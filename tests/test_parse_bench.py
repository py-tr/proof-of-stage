from app.engine import parse_bench as pb


def test_parse2_blocks_converts_tagged_markdown():
    content = (
        "<x_0.2734><y_0.5813>LYMPH NODES: TWO OF EIGHTEEN (2/18)<x_0.7617><y_0.6047><class_List-item>"
        "<x_0.1><y_0.2>Title<x_0.5><y_0.25><class_Title>"
    )
    blocks, leftover = pb.parse2_blocks(content)
    assert not leftover
    assert blocks[0] == {
        "x0": 0.2734,
        "y0": 0.5813,
        "x1": 0.7617,
        "y1": 0.6047,
        "text": "LYMPH NODES: TWO OF EIGHTEEN (2/18)",
        "kind": "List-item",
    }
    assert blocks[1]["kind"] == "Title"


def test_parse2_blocks_flags_a_cut_off_tail():
    blocks, leftover = pb.parse2_blocks(
        "<x_0.1><y_0.2>Done<x_0.5><y_0.3><class_Text><x_0.1><y_0.4>Cut"
    )
    assert len(blocks) == 1 and leftover


def test_value_matches():
    assert pb.value_matches("N", "N1A", "N1")
    assert not pb.value_matches("N", "N2", "N1")
    assert pb.value_matches("NPOS", "4", "4")
    assert pb.value_matches("NPOS", "4.0", "4")
    assert not pb.value_matches("NPOS", None, "4")
