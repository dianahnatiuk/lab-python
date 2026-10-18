"""Тести лабораторного процесу: статуси, ролі, IDOR, PDF.

Потрібні запущені PostgreSQL і MongoDB (docker compose up -d db mongo).
"""

from tests.helpers import auth, login, register_patient

RESULTS = {"values": {"HGB": 135.0, "GLU": 7.2}, "conclusion": "Контроль глюкози"}


def _patient(client, staff) -> dict:
    """Пацієнт з акаунтом: (токен, id картки пацієнта)."""
    user = register_patient(client)
    token = login(client, user["email"])
    r = client.get("/api/v1/patients", headers=auth(staff["receptionist"]))
    assert r.status_code == 200
    patient_id = next(p["id"] for p in r.json() if p["user_id"] == user["id"])
    return {"token": token, "patient_id": patient_id}


def _order(client, staff, patient_id, codes=("HGB", "GLU")) -> dict:
    r = client.post(
        "/api/v1/orders",
        headers=auth(staff["receptionist"]),
        json={"patient_id": patient_id, "test_codes": list(codes)},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _post(client, token, path, **kwargs):
    return client.post(f"/api/v1/orders/{path}", headers=auth(token), **kwargs)


def _complete(client, staff, order_id) -> None:
    assert _post(client, staff["nurse"], f"{order_id}/collect").status_code == 200
    assert _post(client, staff["lab_tech"], f"{order_id}/receive").status_code == 200
    r = _post(client, staff["lab_tech"], f"{order_id}/results", json=RESULTS)
    assert r.status_code == 200, r.text


def test_full_workflow_and_pdf(client, staff):
    p = _patient(client, staff)
    order = _order(client, staff, p["patient_id"])
    oid = order["id"]
    assert order["status"] == "registered"

    assert _post(client, staff["nurse"], f"{oid}/collect").json()["status"] == "collected"
    assert _post(client, staff["lab_tech"], f"{oid}/receive").json()["status"] == "in_lab"
    done = _post(client, staff["lab_tech"], f"{oid}/results", json=RESULTS)
    assert done.json()["status"] == "completed"

    mine = client.get("/api/v1/orders", headers=auth(p["token"])).json()
    assert oid in [o["id"] for o in mine]

    results = client.get(f"/api/v1/orders/{oid}/results", headers=auth(p["token"]))
    assert results.status_code == 200
    flags = {t["code"]: t["flag"] for t in results.json()["tests"]}
    assert flags == {"HGB": "normal", "GLU": "high"}

    detail = client.get(f"/api/v1/orders/{oid}", headers=auth(p["token"])).json()
    assert [h["to_status"] for h in detail["history"]] == [
        "registered",
        "collected",
        "in_lab",
        "completed",
    ]

    pdf = client.get(f"/api/v1/orders/{oid}/pdf", headers=auth(p["token"]))
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")


def test_status_cannot_be_skipped_or_repeated(client, staff):
    oid = _order(client, staff, _patient(client, staff)["patient_id"])["id"]
    # пропуск кроку: лабораторія не може прийняти незабраний матеріал
    assert _post(client, staff["lab_tech"], f"{oid}/receive").status_code == 409
    assert _post(client, staff["lab_tech"], f"{oid}/results", json=RESULTS).status_code == 409
    assert _post(client, staff["nurse"], f"{oid}/collect").status_code == 200
    # повторний перехід
    assert _post(client, staff["nurse"], f"{oid}/collect").status_code == 409


def test_roles_are_enforced_on_transitions(client, staff):
    p = _patient(client, staff)
    oid = _order(client, staff, p["patient_id"])["id"]
    assert _post(client, staff["lab_tech"], f"{oid}/collect").status_code == 403
    assert _post(client, p["token"], f"{oid}/collect").status_code == 403
    assert _post(client, staff["nurse"], f"{oid}/results", json=RESULTS).status_code == 403
    # пацієнт і медсестра не створюють замовлення
    body = {"patient_id": p["patient_id"], "test_codes": ["HGB"]}
    assert client.post("/api/v1/orders", headers=auth(p["token"]), json=body).status_code == 403
    assert client.post("/api/v1/orders", headers=auth(staff["nurse"]), json=body).status_code == 403


def test_anonymous_cannot_use_orders(client):
    assert client.get("/api/v1/orders").status_code == 401
    assert client.get("/api/v1/orders/1/pdf").status_code == 401
    assert client.post("/api/v1/orders/1/collect").status_code == 401


def test_idor_patient_cannot_read_other_order_or_pdf(client, staff):
    a = _patient(client, staff)
    b = _patient(client, staff)
    oid = _order(client, staff, a["patient_id"])["id"]
    _complete(client, staff, oid)

    assert client.get(f"/api/v1/orders/{oid}", headers=auth(b["token"])).status_code == 403
    other = auth(b["token"])
    assert client.get(f"/api/v1/orders/{oid}/results", headers=other).status_code == 403
    assert client.get(f"/api/v1/orders/{oid}/pdf", headers=other).status_code == 403
    listed = client.get("/api/v1/orders", headers=auth(b["token"])).json()
    assert oid not in [o["id"] for o in listed]
    # власник та персонал мають доступ
    owner = auth(a["token"])
    reception = auth(staff["receptionist"])
    assert client.get(f"/api/v1/orders/{oid}/pdf", headers=owner).status_code == 200
    assert client.get(f"/api/v1/orders/{oid}/pdf", headers=reception).status_code == 200


def test_pdf_not_available_before_completion(client, staff):
    p = _patient(client, staff)
    oid = _order(client, staff, p["patient_id"])["id"]
    assert client.get(f"/api/v1/orders/{oid}/pdf", headers=auth(p["token"])).status_code == 409


def test_results_validation(client, staff):
    oid = _order(client, staff, _patient(client, staff)["patient_id"])["id"]
    _post(client, staff["nurse"], f"{oid}/collect")
    _post(client, staff["lab_tech"], f"{oid}/receive")
    missing = _post(client, staff["lab_tech"], f"{oid}/results", json={"values": {"HGB": 130}})
    extra = _post(
        client,
        staff["lab_tech"],
        f"{oid}/results",
        json={"values": {"HGB": 130, "GLU": 5, "TSH": 1}},
    )
    assert missing.status_code == 422
    assert extra.status_code == 422
    # замовлення лишилося в лабораторії
    state = client.get(f"/api/v1/orders/{oid}", headers=auth(staff["lab_tech"])).json()
    assert state["status"] == "in_lab"


def test_order_validation(client, staff):
    p = _patient(client, staff)
    rec = auth(staff["receptionist"])
    pid = p["patient_id"]

    def create(patient_id, codes):
        body = {"patient_id": patient_id, "test_codes": codes}
        return client.post("/api/v1/orders", headers=rec, json=body)

    unknown = create(pid, ["XXX"])
    empty = create(pid, [])
    nobody = create(99999999, ["HGB"])
    assert unknown.status_code == 422
    assert empty.status_code == 422
    assert nobody.status_code == 404


def test_html_pages_render_for_each_role(client, staff):
    p = _patient(client, staff)
    oid = _order(client, staff, p["patient_id"])["id"]
    _post(client, staff["nurse"], f"{oid}/collect")
    _post(client, staff["lab_tech"], f"{oid}/receive")
    for path, token in (
        ("/reception", staff["receptionist"]),
        ("/nurse", staff["nurse"]),
        ("/lab", staff["lab_tech"]),
        (f"/lab/orders/{oid}/results", staff["lab_tech"]),
        ("/patient", p["token"]),
    ):
        r = client.get(path, headers=auth(token))
        assert r.status_code == 200, f"{path}: {r.status_code}"
    # чужа роль не бачить сторінку
    assert client.get("/lab", headers=auth(p["token"])).status_code == 403
    assert client.get("/reception", headers=auth(staff["nurse"])).status_code == 403
