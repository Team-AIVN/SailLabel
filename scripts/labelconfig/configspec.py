"""Parse a Label Studio XML label config into a control spec, and build/validate
prediction results against it.

Single source of truth: the XML. When the XML changes, re-run the generators — the
control names, toName targets, types and valid choice values are all derived here so
predictions can never drift out of sync silently.

Choice matching: a Choice's result value is its ``alias`` when present, else its
``value`` (mirrors the editor: Choice.jsx ``_resultValue = alias ?? value``).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


@dataclass
class Control:
    name: str  # from_name
    to_name: str
    type: str  # 'choices' | 'textarea' | ...
    required: bool = False
    # display value -> result value (alias or value). Empty for free-text controls.
    choices: dict[str, str] = field(default_factory=dict)

    @property
    def valid_result_values(self) -> set[str]:
        return set(self.choices.values())


@dataclass
class ConfigSpec:
    controls: dict[str, Control]  # keyed by from_name
    data_vars: set[str]  # e.g. {'image', 'data'}

    @classmethod
    def from_xml(cls, xml_text: str) -> "ConfigSpec":
        # Strip an XML comment-safe parse; LS configs are plain XML.
        root = ET.fromstring(xml_text)
        controls: dict[str, Control] = {}
        data_vars: set[str] = set()

        # Data variables: any value="$var" on any tag.
        for el in root.iter():
            v = el.attrib.get("value", "")
            m = re.fullmatch(r"\$(\w+)", v.strip())
            if m:
                data_vars.add(m.group(1))

        CONTROL_TAGS = {
            "Choices": "choices",
            "TextArea": "textarea",
            "Labels": "labels",
            "Rating": "rating",
            "Number": "number",
            "DateTime": "datetime",
            "Taxonomy": "taxonomy",
        }
        for el in root.iter():
            ctype = CONTROL_TAGS.get(el.tag)
            if not ctype:
                continue
            name = el.attrib.get("name")
            to_name = el.attrib.get("toName")
            if not name or not to_name:
                continue
            ctrl = Control(
                name=name,
                to_name=to_name,
                type=ctype,
                required=el.attrib.get("required", "").lower() == "true",
            )
            for choice in el.findall(".//Choice"):
                val = choice.attrib.get("value")
                if val is None:
                    continue
                ctrl.choices[val] = choice.attrib.get("alias") or val
            controls[name] = ctrl

        return cls(controls=controls, data_vars=data_vars)

    # --- prediction building ---

    def result_for(self, from_name: str, answer) -> dict:
        """Build one prediction/annotation result entry for a control.

        `answer` is a display value (or list) for choices, or a string for textarea.
        Choice display values are mapped to their alias/result value; invalid values raise.
        """
        ctrl = self.controls.get(from_name)
        if ctrl is None:
            raise KeyError(f"Unknown control: {from_name}")
        entry = {"id": f"{from_name}_p", "from_name": from_name, "to_name": ctrl.to_name, "type": ctrl.type}
        if ctrl.type == "choices":
            answers = answer if isinstance(answer, list) else [answer]
            mapped = []
            for a in answers:
                if a in ctrl.choices:  # given as display value
                    mapped.append(ctrl.choices[a])
                elif a in ctrl.valid_result_values:  # given as alias/result value
                    mapped.append(a)
                else:
                    raise ValueError(f"{from_name}: invalid choice {a!r}; allowed {sorted(ctrl.choices)}")
            entry["value"] = {"choices": mapped}
        elif ctrl.type == "textarea":
            texts = answer if isinstance(answer, list) else [answer]
            entry["value"] = {"text": [str(t) for t in texts]}
        else:
            raise NotImplementedError(f"result_for does not support type {ctrl.type}")
        return entry

    def build_prediction(self, answers: dict, model_version: str = "ai-demo-v1", score: float = 0.9) -> dict:
        """answers: {from_name: display_value_or_list/str}. Returns a task-format prediction."""
        result = [self.result_for(fn, ans) for fn, ans in answers.items()]
        return {"model_version": model_version, "score": score, "result": result}

    # --- validation ---

    def validate_prediction(self, prediction: dict) -> list[str]:
        """Return a list of human-readable problems (empty = valid)."""
        problems: list[str] = []
        for r in prediction.get("result", []):
            fn = r.get("from_name")
            ctrl = self.controls.get(fn)
            if ctrl is None:
                problems.append(f"from_name '{fn}' is not a control in this config")
                continue
            if r.get("to_name") != ctrl.to_name:
                problems.append(f"{fn}: to_name '{r.get('to_name')}' != expected '{ctrl.to_name}'")
            if r.get("type") != ctrl.type:
                problems.append(f"{fn}: type '{r.get('type')}' != expected '{ctrl.type}'")
            if ctrl.type == "choices":
                for c in r.get("value", {}).get("choices", []):
                    if c not in ctrl.valid_result_values:
                        problems.append(f"{fn}: choice '{c}' not allowed (allowed: {sorted(ctrl.valid_result_values)})")
        return problems

    def required_controls(self) -> list[str]:
        return [n for n, c in self.controls.items() if c.required]
