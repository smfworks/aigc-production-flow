from app.gates import all_gates_green, evaluate_gates
from tests.fixtures import empty_pack, green_pack, red_haft_pack


def _by_id(pack, gate_id: str):
    return next(gate for gate in evaluate_gates(pack) if gate["id"] == gate_id)


def test_empty_pack_is_all_red():
    pack = empty_pack()
    gates = evaluate_gates(pack)
    assert len(gates) == 11
    assert all(not gate["ok"] for gate in gates)
    assert all_gates_green(pack) is False


def test_green_pack_clears_all_gates():
    pack = green_pack()
    red = [gate for gate in evaluate_gates(pack) if not gate["ok"]]
    assert red == []
    assert all_gates_green(pack) is True


def test_entity_schedule_and_lock_diff_gates():
    pack = green_pack()
    pack["editList"][0]["entities"] = ""
    assert _by_id(pack, "entity-schedule")["ok"] is False
    pack = green_pack()
    pack["characters"][0]["lockParagraph"] = "Same face, brown hair every hop."
    pack["stills"][0]["lockFromStill"] = "Brunette hair locked from this still."
    assert _by_id(pack, "lock-diff")["ok"] is False
    assert "brunette" in _by_id(pack, "lock-diff")["detail"]


def test_unpinned_haft_keeps_props_red():
    pack = red_haft_pack()
    assert all_gates_green(pack) is False
    assert _by_id(pack, "props")["ok"] is False
    assert "haft" in _by_id(pack, "props")["detail"]


def test_wikipedia_is_not_a_still():
    pack = green_pack()
    pack["characters"][0]["stillFile"] = "https://en.wikipedia.org/wiki/Francisca"
    assert _by_id(pack, "characters")["ok"] is False


def test_map_rejects_shots():
    pack = green_pack()
    pack["map"][0]["beat"] = "CU of axe"
    pack["map"][0]["clock"] = "shot 1"
    assert _by_id(pack, "map")["ok"] is False
