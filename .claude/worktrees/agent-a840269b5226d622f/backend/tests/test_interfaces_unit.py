"""Unit — interface engine chỉ là contract, chưa có logic AI (M1 §3.1)."""
import pytest

from app.services.interfaces import (
    BBox,
    IDetector,
    IInpainter,
    IOCREngine,
    ITranslator,
    ITypesetter,
    UnimplementedDetector,
    UnimplementedInpainter,
    UnimplementedOCREngine,
    UnimplementedTranslator,
    UnimplementedTypesetter,
)


def test_bbox_la_dataclass_bat_bien():
    b = BBox(x=1.0, y=2.0, w=3.0, h=4.0)
    assert (b.x, b.y, b.w, b.h) == (1.0, 2.0, 3.0, 4.0)
    with pytest.raises(Exception):
        b.x = 9.0


@pytest.mark.parametrize(
    "impl,proto,method,args",
    [
        (UnimplementedDetector(), IDetector, "detect", ("a.png",)),
        (UnimplementedOCREngine(), IOCREngine, "recognize", ("a.png", BBox(0, 0, 1, 1))),
        (UnimplementedInpainter(), IInpainter, "inpaint", ("a.png", [BBox(0, 0, 1, 1)])),
        (UnimplementedTranslator(), ITranslator, "translate", (["x"], "ja", "vi")),
        (UnimplementedTypesetter(), ITypesetter, "fit", ("x", BBox(0, 0, 1, 1), "HLCOMIC2")),
    ],
)
def test_stub_engine_khop_protocol_va_bao_loi_ro_rang(impl, proto, method, args):
    assert isinstance(impl, proto)
    with pytest.raises(NotImplementedError):
        getattr(impl, method)(*args)
