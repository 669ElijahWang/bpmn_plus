#!/usr/bin/env python3
import sys
import os
import re
import glob
import uuid

# Default sizes for elements
DIMENSIONS = {
    "startEvent": (36, 36),
    "endEvent": (36, 36),
    "userTask": (100, 80),
    "exclusiveGateway": (50, 50),
    "parallelGateway": (50, 50),
    "task": (100, 80),
}
DEFAULT_SIZE = (100, 80)

FLOW_NODE_TAGS = [
    "startEvent", "endEvent", "userTask", "serviceTask", "scriptTask",
    "sendTask", "receiveTask", "manualTask", "businessRuleTask", "task",
    "exclusiveGateway", "parallelGateway", "inclusiveGateway",
    "eventBasedGateway", "complexGateway", "subProcess", "callActivity",
    "intermediateCatchEvent", "intermediateThrowEvent", "boundaryEvent",
]

# Custom non-standard tags that should be mapped to standard BPMN types
CUSTOM_TAG_MAP = {
    "countersignTask": "userTask",
    "multiInstanceTask": "userTask",
}

def perform_conversion(content, filename):
    """Core logic to convert BPMN content."""
    try:
        data = parse_file_content(content)
        if not data["processes"]:
            print(f"Warning: No processes found in {filename}")
            return None
        xml_output = build_bpmn(data)
        return xml_output
    except Exception as e:
        print(f"Conversion error in {filename}: {e}")
        return None

def parse_file_content(content):
    data = {"definitions_id": "Definitions_1", "processes": [], "shapes": []}

    # Extract definitions basics
    def_match = re.search(r'<(?:\w+:)?definitions\b([^>]*)>', content, re.DOTALL)
    if def_match:
        attrs = def_match.group(1)
        data["definitions_id"] = _extract_attr(attrs, "id") or "Definitions_1"

    # Extract process blocks
    process_pattern = re.compile(r'<(?:\w+:)?process\b([^>]*)>(.*?)</(?:\w+:)?process>', re.DOTALL)
    for proc_match in process_pattern.finditer(content):
        proc_attrs = proc_match.group(1).strip()
        proc_body = proc_match.group(2)
        proc = {
            "id": _extract_attr(proc_attrs, "id") or f"Process_{uuid.uuid4().hex[:7]}",
            "name": _extract_attr(proc_attrs, "name") or "Process_Name",
            "elements": [],
            "flows": [],
        }

        # Parse nodes
        for tag_name in FLOW_NODE_TAGS:
            # Normal blocks
            node_pattern = re.compile(rf'<(?:\w+:)?{tag_name}\b([^>]*)>(.*?)</(?:\w+:)?{tag_name}>', re.DOTALL)
            for m in node_pattern.finditer(proc_body):
                attrs, body = m.group(1), m.group(2)
                if attrs.rstrip().endswith('/'): continue
                elem = {
                    "type": tag_name, "id": _extract_attr(attrs, "id") or "", 
                    "name": _extract_attr(attrs, "name") or "",
                    "incoming": re.findall(r'<(?:\w+:)?incoming>(.*?)</(?:\w+:)?incoming>', body),
                    "outgoing": re.findall(r'<(?:\w+:)?outgoing>(.*?)</(?:\w+:)?outgoing>', body),
                }
                if elem["id"]: proc["elements"].append(elem)
            
            # Self-closing
            sc_pattern = re.compile(rf'<(?:\w+:)?{tag_name}\b([^>]*)/>', re.DOTALL)
            for m in sc_pattern.finditer(proc_body):
                attrs = m.group(1)
                elem = {"type": tag_name, "id": _extract_attr(attrs, "id") or "", "name": _extract_attr(attrs, "name") or "", "incoming": [], "outgoing": []}
                if elem["id"] and elem["id"] not in {e["id"] for e in proc["elements"]}:
                    proc["elements"].append(elem)

        # Parse custom/non-standard tags (e.g. countersignTask inside extensionElements)
        existing_ids = {e["id"] for e in proc["elements"]}
        for custom_tag, mapped_type in CUSTOM_TAG_MAP.items():
            custom_pattern = re.compile(rf'<(?:\w+:)?{custom_tag}\b([^>]*)>(.*?)</(?:\w+:)?{custom_tag}>', re.DOTALL)
            for m in custom_pattern.finditer(proc_body):
                attrs, body = m.group(1), m.group(2)
                eid = _extract_attr(attrs, "id") or ""
                if eid and eid not in existing_ids:
                    elem = {
                        "type": mapped_type, "id": eid,
                        "name": _extract_attr(attrs, "name") or "",
                        "incoming": re.findall(r'<(?:\w+:)?incoming>(.*?)</(?:\w+:)?incoming>', body),
                        "outgoing": re.findall(r'<(?:\w+:)?outgoing>(.*?)</(?:\w+:)?outgoing>', body),
                    }
                    proc["elements"].append(elem)
                    existing_ids.add(eid)

        # Parse flows
        flow_pattern = re.compile(r'<(?:\w+:)?sequenceFlow\b([^>]*)(?:>(.*?)</(?:\w+:)?sequenceFlow>|/>)', re.DOTALL)
        for m in flow_pattern.finditer(proc_body):
            attrs, body = m.group(1), m.group(2) or ""
            flow = {
                "id": _extract_attr(attrs, "id") or f"Flow_{uuid.uuid4().hex[:7]}",
                "sourceRef": _extract_attr(attrs, "sourceRef") or "",
                "targetRef": _extract_attr(attrs, "targetRef") or "",
                "name": _extract_attr(attrs, "name") or "",
            }
            cond = re.search(r'<(?:\w+:)?conditionExpression[^>]*>(.*?)</(?:\w+:)?conditionExpression>', body, re.DOTALL)
            if cond: flow["condition"] = cond.group(1).strip()
            if flow["id"]: proc["flows"].append(flow)
        
        data["processes"].append(proc)

    # Extract Shapes
    shape_pattern = re.compile(r'<(?:\w+:)?BPMNShape\b([^>]*)>.*?\b(?:\w+:)?Bounds\b([^>]*)/?>', re.DOTALL)
    for m in shape_pattern.finditer(content):
        s_attrs, b_attrs = m.group(1), m.group(2)
        shape = {
            "bpmnElement": _extract_attr(s_attrs, "bpmnElement") or "",
            "id": _extract_attr(s_attrs, "id") or f"Shape_{uuid.uuid4().hex[:7]}",
            "x": _extract_int_attr(b_attrs, "x"), "y": _extract_int_attr(b_attrs, "y"),
            "width": _extract_int_attr(b_attrs, "width"), "height": _extract_int_attr(b_attrs, "height"),
        }
        if shape["bpmnElement"]: data["shapes"].append(shape)

    return data

def _extract_attr(attrs, name):
    m = re.search(rf'\b{name}="([^"]*)"', attrs)
    return m.group(1) if m else None

def _extract_int_attr(attrs, name):
    v = _extract_attr(attrs, name)
    try: return int(float(v)) if v else None
    except: return None

def _esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;") if t else ""

def build_bpmn(data):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:zeebe="http://camunda.org/schema/zeebe/1.0" xmlns:di="http://www.omg.org/spec/DD/20100524/DI" xmlns:modeler="http://camunda.org/schema/modeler/1.0" id="Definitions_1" targetNamespace="http://bpmn.io/schema/bpmn" exporter="Camunda Modeler" exporterVersion="5.42.0" modeler:executionPlatform="Camunda Cloud" modeler:executionPlatformVersion="8.8.0">')

    # Prep coordinate offset
    if data["shapes"]:
        xs = [s["x"] for s in data["shapes"] if s["x"] is not None]
        ys = [s["y"] for s in data["shapes"] if s["y"] is not None]
        off_x = max(0, 100 - min(xs)) if xs else 0
        off_y = max(0, 100 - min(ys)) if ys else 0
    else: off_x, off_y = 0, 0

    shape_map = {}
    gateways = set()
    for proc in data["processes"]:
        for e in proc["elements"]:
            if "Gateway" in e["type"]: gateways.add(e["id"])
            shape_map[e["id"]] = {"type": e["type"]}

    for s in data["shapes"]:
        stype = shape_map.get(s["bpmnElement"], {}).get("type", "task")
        dw, dh = DIMENSIONS.get(stype, DEFAULT_SIZE)
        if s["bpmnElement"] in shape_map:
            shape_map[s["bpmnElement"]].update({
                "id": f"{s['bpmnElement']}_di",
                "x": (s["x"] or 0) + off_x, "y": (s["y"] or 0) + off_y,
                "w": s["width"] or dw, "h": s["height"] or dh
            })

    for proc in data["processes"]:
        lines.append(f'  <bpmn:process id="{_esc(proc["id"])}" name="{_esc(proc["name"])}" isExecutable="true">')
        for e in proc["elements"]:
            tag = f'bpmn:{e["type"]}'
            n_attr = f' name="{_esc(e["name"])}"' if e["name"] else ""
            lines.append(f'    <{tag} id="{_esc(e["id"])}"{n_attr}>')
            for inc in e["incoming"]: lines.append(f'      <bpmn:incoming>{_esc(inc)}</bpmn:incoming>')
            for out in e["outgoing"]: lines.append(f'      <bpmn:outgoing>{_esc(out)}</bpmn:outgoing>')
            lines.append(f'    </{tag}>')
        
        for f in proc["flows"]:
            n_attr = f' name="{_esc(f["name"])}"' if f["name"] else ""
            lines.append(f'    <bpmn:sequenceFlow id="{_esc(f["id"])}" sourceRef="{_esc(f["sourceRef"])}" targetRef="{_esc(f["targetRef"])}"{n_attr}>')
            if f.get("condition") and f["sourceRef"] in gateways:
                cond = f["condition"] if f["condition"].startswith("=") else f'={f["condition"]}'
                lines.append(f'      <bpmn:conditionExpression xsi:type="bpmn:tFormalExpression">{_esc(cond)}</bpmn:conditionExpression>')
            lines.append('    </bpmn:sequenceFlow>')
        lines.append('  </bpmn:process>')

    if data["processes"]:
        lines.append('  <bpmndi:BPMNDiagram id="BPMNDiagram_1">')
        lines.append(f'    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="{_esc(data["processes"][0]["id"])}">')
        for eid, s in shape_map.items():
            if "x" in s:
                lines.append(f'      <bpmndi:BPMNShape id="{_esc(s["id"])}" bpmnElement="{_esc(eid)}">')
                lines.append(f'        <dc:Bounds x="{int(s["x"])}" y="{int(s["y"])}" width="{int(s["w"])}" height="{int(s["h"])}" />')
                lines.append('      </bpmndi:BPMNShape>')
        for proc in data["processes"]:
            for f in proc["flows"]:
                src, tgt = shape_map.get(f["sourceRef"]), shape_map.get(f["targetRef"])
                if src and tgt and "x" in src and "x" in tgt:
                    lines.append(f'      <bpmndi:BPMNEdge id="{_esc(f["id"])}_di" bpmnElement="{_esc(f["id"])}">')
                    lines.append(f'        <di:waypoint x="{int(src["x"] + src["w"])}" y="{int(src["y"] + src["h"]//2)}" />')
                    lines.append(f'        <di:waypoint x="{int(tgt["x"])}" y="{int(tgt["y"] + tgt["h"]//2)}" />')
                    lines.append('      </bpmndi:BPMNEdge>')
        lines.append('    </bpmndi:BPMNPlane>')
        lines.append('  </bpmndi:BPMNDiagram>')
    lines.append('</bpmn:definitions>')
    return "\n".join(lines)

def convert_file(inp):
    try:
        with open(inp, "r", encoding="utf-8") as f:
            content = f.read()
        xml = perform_conversion(content, inp)
        if xml:
            out = f"{os.path.splitext(inp)[0]}_camunda.bpmn"
            with open(out, "w", encoding="utf-8") as f: f.write(xml)
            print(f"✓ {inp} -> {out}")
            return True
    except Exception as e:
        print(f"Error converting {inp}: {e}")
    return False

if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(1)
    for arg in sys.argv[1:]:
        if os.path.isdir(arg):
            for f in glob.glob(os.path.join(arg, "*.bpmn")):
                if "_camunda" not in f: convert_file(f)
        else: convert_file(arg)
