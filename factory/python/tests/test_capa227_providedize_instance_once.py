"""CAPA-227 (feature 016 factory-HAL review 2026-11-11): providedize inserted the instance into every provided LL
call, also when the profile text already passed it: hand wwdg.yaml examples became LL_WWDG_SetPrescaler(WWDG, WWDG, ..)
in real HAL prompts. A call that already starts with the instance is left as it is."""
from forge_factory.workflow import prompts as P


def _api(monkeypatch):
    api = {"instance": "WWDG", "functions": ["LL_WWDG_SetPrescaler", "LL_WWDG_Enable"],
           "calls": {"LL_WWDG_SetPrescaler": "LL_WWDG_SetPrescaler(WWDG, p)", "LL_WWDG_Enable": "LL_WWDG_Enable(WWDG)"},
           "signatures": {"LL_WWDG_SetPrescaler": "void LL_WWDG_SetPrescaler(WWDG_TypeDef *WWDGx, uint32_t p)",
                          "LL_WWDG_Enable": "void LL_WWDG_Enable(WWDG_TypeDef *WWDGx)"}}
    monkeypatch.setitem(P.PROVIDED_API, "api", api)
    monkeypatch.setitem(P.LAYER, "layer", "HAL")
    monkeypatch.setattr(P, "provided_registers", lambda text, api: text)


def test_a_call_that_already_passes_the_instance_is_unchanged(monkeypatch):
    _api(monkeypatch)
    out = P.providedize("LL_WWDG_SetPrescaler(WWDG, LL_WWDG_PRESCALER_8); LL_WWDG_Enable( WWDG );")
    assert "WWDG, WWDG" not in out and "LL_WWDG_SetPrescaler(WWDG, LL_WWDG_PRESCALER_8)" in out
    assert "LL_WWDG_Enable( WWDG )" in out


def test_a_greenfield_call_still_gets_the_instance(monkeypatch):
    _api(monkeypatch)
    out = P.providedize("LL_WWDG_SetPrescaler(LL_WWDG_PRESCALER_8); LL_WWDG_Enable();")
    assert "LL_WWDG_SetPrescaler(WWDG, LL_WWDG_PRESCALER_8)" in out and "LL_WWDG_Enable(WWDG)" in out
