import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Pedigree Drawer (Family Blocks)", layout="wide")

# =============================
# 默认示例数据（含 spouse_id）
# =============================
DEFAULT_ROWS = [
    # 祖辈（父系 / 母系）
    {"id":"P4","name":"祖父(父系)","sex":"M","affected":True,  "deceased":True,  "father_id":"","mother_id":"","spouse_id":"P5","proband":False,"birth_order":None},
    {"id":"P5","name":"祖母(父系)","sex":"F","affected":False, "deceased":False, "father_id":"","mother_id":"","spouse_id":"P4","proband":False,"birth_order":None},
    {"id":"P6","name":"外祖父","sex":"M","affected":False, "deceased":False, "father_id":"","mother_id":"","spouse_id":"P7","proband":False,"birth_order":None},
    {"id":"P7","name":"外祖母","sex":"F","affected":True,  "deceased":True,  "father_id":"","mother_id":"","spouse_id":"P6","proband":False,"birth_order":None},

    # 父母
    {"id":"P2","name":"父亲","sex":"M","affected":False, "deceased":False, "father_id":"P4","mother_id":"P5","spouse_id":"P3","proband":False,"birth_order":None},
    {"id":"P3","name":"母亲","sex":"F","affected":False, "deceased":False, "father_id":"P6","mother_id":"P7","spouse_id":"P2","proband":False,"birth_order":None},

    # 同胞（按出生顺序）
    {"id":"P8","name":"姐姐","sex":"F","affected":False, "deceased":False, "father_id":"P2","mother_id":"P3","spouse_id":"P14","proband":False,"birth_order":1},
    {"id":"P1","name":"患者","sex":"F","affected":True,  "deceased":False, "father_id":"P2","mother_id":"P3","spouse_id":"P11","proband":True, "birth_order":2},
    {"id":"P9","name":"弟弟","sex":"M","affected":True,  "deceased":True,  "father_id":"P2","mother_id":"P3","spouse_id":"","proband":False,"birth_order":3},
    {"id":"P10","name":"妹妹","sex":"F","affected":True, "deceased":True,  "father_id":"P2","mother_id":"P3","spouse_id":"P16","proband":False,"birth_order":4},

    # 配偶（无子代也能显示）
    {"id":"P11","name":"配偶","sex":"M","affected":False, "deceased":False, "father_id":"","mother_id":"","spouse_id":"P1","proband":False,"birth_order":None},
    {"id":"P14","name":"姐夫","sex":"M","affected":False, "deceased":False, "father_id":"","mother_id":"","spouse_id":"P8","proband":False,"birth_order":None},
    {"id":"P16","name":"妹夫","sex":"M","affected":False, "deceased":False, "father_id":"","mother_id":"","spouse_id":"P10","proband":False,"birth_order":None},

    # 患者子代
    {"id":"P12","name":"儿子","sex":"M","affected":False, "deceased":False, "father_id":"P11","mother_id":"P1","spouse_id":"","proband":False,"birth_order":1},
    {"id":"P13","name":"女儿","sex":"F","affected":False, "deceased":False, "father_id":"P11","mother_id":"P1","spouse_id":"","proband":False,"birth_order":2},

    # 姐姐子代
    {"id":"P15","name":"侄子","sex":"M","affected":False, "deceased":False, "father_id":"P14","mother_id":"P8","spouse_id":"","proband":False,"birth_order":1},
]

# =============================
# 基础工具
# =============================
def to_bool(v):
    if isinstance(v, bool):
        return v
    if pd.isna(v):
        return False
    return str(v).strip().lower() in ["true", "1", "yes", "y", "是"]

def to_int_or_none(v):
    if pd.isna(v):
        return None
    s = str(v).strip()
    if s == "":
        return None
    try:
        return int(float(s))
    except Exception:
        return None

def clean_id(v):
    if pd.isna(v):
        return None
    s = str(v).strip()
    return s if s else None

def df_to_people(df: pd.DataFrame):
    rows = []
    for _, r in df.iterrows():
        pid = clean_id(r.get("id", ""))
        if not pid:
            continue
        rows.append({
            "id": pid,
            "name": str(r.get("name", "")).strip() or pid,
            "sex": (str(r.get("sex", "U")).strip().upper() or "U"),
            "affected": to_bool(r.get("affected", False)),
            "deceased": to_bool(r.get("deceased", False)),
            "father_id": clean_id(r.get("father_id", "")),
            "mother_id": clean_id(r.get("mother_id", "")),
            "spouse_id": clean_id(r.get("spouse_id", "")),
            "proband": to_bool(r.get("proband", False)),
            "birth_order": to_int_or_none(r.get("birth_order", None)),
        })
    return rows

def get_person_map(people):
    return {p["id"]: p for p in people}

def find_proband_id(people):
    for p in people:
        if p.get("proband"):
            return p["id"]
    return None

# =============================
# 校验
# =============================
def validate_people(people):
    ids = [p.get("id") for p in people]
    if any(not i for i in ids):
        raise ValueError("每个人都必须有 id。")
    if len(ids) != len(set(ids)):
        raise ValueError("存在重复 id（id 不能重复）。")

    person_map = get_person_map(people)
    id_set = set(person_map.keys())

    for p in people:
        if p["sex"] not in ["M", "F", "U"]:
            raise ValueError(f"{p['id']} 的 sex 必须是 M/F/U。")
        for k in ["father_id", "mother_id", "spouse_id"]:
            v = p.get(k)
            if v and v not in id_set:
                raise ValueError(f"{p['id']} 的 {k}={v} 不存在。")
        if p.get("spouse_id") == p["id"]:
            raise ValueError(f"{p['id']} 的 spouse_id 不能指向自己。")

    # spouse_id 对称
    for p in people:
        sid = p.get("spouse_id")
        if sid:
            other = person_map[sid]
            if other.get("spouse_id") != p["id"]:
                raise ValueError(
                    f"婚配关系需成对填写：{p['id']}.spouse_id={sid}，但 {sid}.spouse_id 不是 {p['id']}"
                )

    # proband 最多一个
    probands = [p["id"] for p in people if p.get("proband")]
    if len(probands) > 1:
        raise ValueError(f"只能有一个患者（proband=True），当前有多个：{probands}")

    # 同父同母 children 的 birth_order 不重复
    fam_orders = {}
    for p in people:
        fid, mid, bo = p.get("father_id"), p.get("mother_id"), p.get("birth_order")
        if fid and mid and bo is not None:
            key = (fid, mid)
            fam_orders.setdefault(key, set())
            if bo in fam_orders[key]:
                raise ValueError(f"同一父母({fid},{mid})下出现重复 birth_order={bo}")
            fam_orders[key].add(bo)

# =============================
# 代际 / 家庭结构
# =============================
def compute_generations(people):
    person_map = get_person_map(people)
    gen = {}

    def get_gen(pid, visiting=None):
        if pid in gen:
            return gen[pid]
        if visiting is None:
            visiting = set()
        if pid in visiting:
            return 0
        visiting.add(pid)

        p = person_map[pid]
        parent_gens = []
        for k in ["father_id", "mother_id"]:
            par = p.get(k)
            if par in person_map:
                parent_gens.append(get_gen(par, visiting))
        g = 0 if not parent_gens else max(parent_gens) + 1
        gen[pid] = g
        visiting.remove(pid)
        return g

    for pid in person_map:
        get_gen(pid)
    return gen

def build_child_families(people):
    """
    child_fams[(father_id, mother_id)] = [child_ids...]
    """
    person_map = get_person_map(people)

    def child_sort_key(cid):
        bo = person_map[cid].get("birth_order")
        return (bo is None, bo if bo is not None else 999999, cid)

    fams = {}
    for p in people:
        fid, mid = p.get("father_id"), p.get("mother_id")
        if fid and mid:
            fams.setdefault((fid, mid), []).append(p["id"])

    for k in fams:
        fams[k] = sorted(fams[k], key=child_sort_key)
    return fams

def build_spouse_pairs(people):
    seen = set()
    pairs = []
    for p in people:
        a = p["id"]
        b = p.get("spouse_id")
        if not b:
            continue
        key = tuple(sorted([a, b]))
        if key in seen:
            continue
        seen.add(key)
        pairs.append(key)
    return pairs

def person_children_map(child_fams):
    m = {}
    for (fid, mid), _children in child_fams.items():
        m.setdefault(fid, []).append((fid, mid))
        m.setdefault(mid, []).append((fid, mid))
    return m

# =============================
# 家庭块布局（核心）
# =============================
def build_sibling_blocks(sibling_ids, person_map, child_fams, x_gap=160, spouse_gap=105, block_gap=120):
    """
    同胞层按“家庭块”排，而不是按单人排。
    """
    p2fams = person_children_map(child_fams)
    blocks = []

    for sid in sibling_ids:
        sp = person_map[sid].get("spouse_id")
        fam_keys = p2fams.get(sid, [])

        preferred = None
        if sp:
            for k in fam_keys:
                if set(k) == set([sid, sp]):
                    preferred = k
                    break
        if preferred is None and fam_keys:
            preferred = fam_keys[0]

        children = child_fams.get(preferred, []) if preferred else []

        # 宽度估算：要能容纳夫妻 + 子代展开
        couple_w = spouse_gap if sp else 0
        child_w = (len(children) - 1) * x_gap if len(children) >= 2 else 0
        width = max(90, couple_w, child_w) + block_gap

        blocks.append({
            "anchor": sid,
            "spouse": sp,
            "family_key": preferred,
            "children": children,
            "width": width,
        })

    return blocks

def structured_layout(people):
    validate_people(people)
    person_map = get_person_map(people)
    gen = compute_generations(people)
    child_fams = build_child_families(people)

    # ---- 参数（留白优先）----
    x_gap = 165            # 同胞/子代间距
    y_gap = 255            # 代际间距
    spouse_gap = 110       # 夫妻中心间距
    margin_x = 120
    margin_y = 110
    upper_side_gap = 220   # 祖辈块左右间距
    block_gap = 125        # 同胞家庭块间距（关键）
    reserve_gap = 240
    # ------------------------

    coords = {}
    proband_id = find_proband_id(people)

    if not proband_id:
        return fallback_layout(people, gen, child_fams, x_gap, y_gap, margin_x, margin_y)

    proband = person_map[proband_id]
    father_id = proband.get("father_id")
    mother_id = proband.get("mother_id")

    # 核心原生家庭同胞
    if father_id and mother_id and (father_id, mother_id) in child_fams:
        sibling_ids = child_fams[(father_id, mother_id)][:]
    else:
        sibling_ids = [proband_id]
    if proband_id not in sibling_ids:
        sibling_ids.append(proband_id)

    sibling_ids = sorted(sibling_ids, key=lambda pid: (
        person_map[pid].get("birth_order") is None,
        person_map[pid].get("birth_order") if person_map[pid].get("birth_order") is not None else 999999,
        pid
    ))

    # 层级
    y_gp = margin_y
    y_parents = margin_y + y_gap
    y_sibs = margin_y + 2 * y_gap
    y_desc = margin_y + 3 * y_gap

    cx = margin_x + 760  # 中间基准

    # 1) 父母居中
    if father_id:
        coords[father_id] = (cx - spouse_gap / 2, y_parents)
    if mother_id:
        coords[mother_id] = (cx + spouse_gap / 2, y_parents)

    if father_id in coords and mother_id in coords:
        sib_center_x = (coords[father_id][0] + coords[mother_id][0]) / 2
    else:
        sib_center_x = cx

    # 2) 同胞层：家庭块布局
    blocks = build_sibling_blocks(
        sibling_ids, person_map, child_fams, x_gap=x_gap, spouse_gap=spouse_gap, block_gap=block_gap
    )

    total_w = sum(b["width"] for b in blocks) if blocks else 0
    start_x = sib_center_x - total_w / 2

    cursor = start_x
    for b in blocks:
        sid = b["anchor"]
        sp = b["spouse"]
        block_center = cursor + b["width"] / 2

        if sp:
            # 简单稳定：本人左、配偶右
            coords[sid] = (block_center - spouse_gap / 2, y_sibs)
            coords[sp] = (block_center + spouse_gap / 2, y_sibs)
        else:
            coords[sid] = (block_center, y_sibs)

        cursor += b["width"]

    # 3) 父系祖辈
    if father_id and father_id in person_map:
        ff = person_map[father_id].get("father_id")
        fm = person_map[father_id].get("mother_id")
        if ff and fm:
            fx, _ = coords[father_id]
            coords[ff] = (fx - upper_side_gap / 2, y_gp)
            coords[fm] = (fx + upper_side_gap / 2, y_gp)

    # 4) 母系祖辈
    if mother_id and mother_id in person_map:
        mf = person_map[mother_id].get("father_id")
        mm = person_map[mother_id].get("mother_id")
        if mf and mm:
            mx, _ = coords[mother_id]
            coords[mf] = (mx - upper_side_gap / 2, y_gp)
            coords[mm] = (mx + upper_side_gap / 2, y_gp)

    # 5) 同胞各自子代：按 block 的家庭中心展开
    for b in blocks:
        fam_key = b["family_key"]
        children = b["children"]
        if not fam_key or not children:
            continue

        fid, mid = fam_key
        if fid not in coords or mid not in coords:
            continue

        center_x = (coords[fid][0] + coords[mid][0]) / 2
        n = len(children)
        start_x_children = center_x - ((n - 1) * x_gap) / 2
        for i, cid in enumerate(children):
            coords[cid] = (start_x_children + i * x_gap, y_desc)

    # 6) spouse_id 兜底：若有已定位人物的配偶未定位，贴旁边（很少触发）
    changed = True
    loops = 0
    while changed and loops < 3:
        changed = False
        loops += 1
        for p in people:
            a = p["id"]
            b = p.get("spouse_id")
            if not b:
                continue
            if a in coords and b not in coords:
                ax, ay = coords[a]
                tx = ax + spouse_gap
                if any(abs(ox - tx) < 75 and abs(oy - ay) < 8 for pid2, (ox, oy) in coords.items() if pid2 != a):
                    tx = ax - spouse_gap
                coords[b] = (tx, ay)
                changed = True

    # 7) 其余未定位放右侧备用区（避免串主线）
    unplaced = [p["id"] for p in people if p["id"] not in coords]
    if unplaced:
        reserve_x = (max(x for x, _ in coords.values()) + reserve_gap) if coords else 1200
        by_gen = {}
        for pid in unplaced:
            by_gen.setdefault(gen.get(pid, 0), []).append(pid)
        for g in sorted(by_gen.keys()):
            y = margin_y + g * y_gap
            x = reserve_x
            for pid in sorted(by_gen[g]):
                coords[pid] = (x, y)
                x += x_gap

    # 8) 画布尺寸
    xs = [x for x, _ in coords.values()] if coords else [0]
    ys = [y for _, y in coords.values()] if coords else [0]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    if min_x < 60:
        shift = 70 - min_x
        for pid in list(coords.keys()):
            x, y = coords[pid]
            coords[pid] = (x + shift, y)
        max_x += shift

    width = int(max_x + 280)
    height = int(max_y + 330)  # 底部留空间给标签

    return coords, child_fams, width, height, gen

def fallback_layout(people, gen, child_fams, x_gap, y_gap, margin_x, margin_y):
    coords = {}
    gen_to_ids = {}
    for p in people:
        gen_to_ids.setdefault(gen[p["id"]], []).append(p["id"])
    for g in sorted(gen_to_ids.keys()):
        y = margin_y + g * y_gap
        x = margin_x
        for pid in sorted(gen_to_ids[g]):
            coords[pid] = (x, y)
            x += x_gap
    max_x = max(x for x, _ in coords.values()) if coords else 1000
    max_y = max(y for _, y in coords.values()) if coords else 700
    return coords, child_fams, int(max_x + 260), int(max_y + 300), gen

# =============================
# SVG 绘制
# =============================
def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def line(x1, y1, x2, y2, w=2.5):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="black" stroke-width="{w}" />'

def choose_arrow_anchor(x, y, width, height, used=None):
    """箭头短一点（按你的要求）"""
    if used is None:
        used = []
    candidates = [
        (x - 105, y - 72, x - 28, y - 20),
        (x + 105, y - 72, x + 28, y - 20),
        (x - 105, y + 72, x - 28, y + 20),
        (x + 105, y + 72, x + 28, y + 20),
    ]
    def score(c):
        tx1, ty1, tx2, ty2 = c
        penalty = 0
        if tx1 < 10 or tx1 > width - 10 or ty1 < 45 or ty1 > height - 10:
            penalty += 1000
        for ex, ey in used:
            if (tx1-ex)**2 + (ty1-ey)**2 < 95**2:
                penalty += 250
        if ty1 > y:
            penalty += 20
        return penalty
    return min(candidates, key=score)

def compute_label_positions(people, coords, base_offset=58, near_x_threshold=115):
    """
    标签更贴近图形底部（按你的要求）
    同层太近时轻微错位，避免重叠
    """
    rows = {}
    for p in people:
        pid = p["id"]
        if pid not in coords:
            continue
        x, y = coords[pid]
        rows.setdefault(round(y), []).append((pid, x, y))

    label_pos = {}
    for _row_y, items in rows.items():
        items.sort(key=lambda t: t[1])
        cluster = []
        clusters = []

        for item in items:
            if not cluster:
                cluster = [item]
            else:
                prev = cluster[-1]
                if abs(item[1] - prev[1]) < near_x_threshold:
                    cluster.append(item)
                else:
                    clusters.append(cluster)
                    cluster = [item]
        if cluster:
            clusters.append(cluster)

        for cl in clusters:
            for i, (pid, x, y) in enumerate(cl):
                extra = 0
                if len(cl) > 1:
                    # 轻微错位，不要太夸张
                    pattern = [0, 14, 26, 14, 26, 38]
                    extra = pattern[i] if i < len(pattern) else 14 * (i % 3)
                label_pos[pid] = (x, y + base_offset + extra)

    return label_pos

def pedigree_to_svg(people, title="Pedigree", show_labels=True):
    validate_people(people)
    coords, child_fams, width, height, _gen = structured_layout(people)

    # 参数（按你这次要求调整）
    r = 26
    base_stroke = 2.6
    proband_stroke = 3.8
    spouse_line_w = 2.4
    label_font = 13

    label_offset = 58      # 文字更靠近图形底部
    child_bar_drop = 68    # 蓝线长一点 / 红线短一点（关键）

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="background:white">'
    )
    svg.append(
        f'<text x="{width/2}" y="42" text-anchor="middle" font-size="22" '
        f'font-family="Arial, Microsoft YaHei">{esc(title)}</text>'
    )

    # 1) 夫妻线（spouse_id）
    for a, b in build_spouse_pairs(people):
        if a not in coords or b not in coords:
            continue
        ax, ay = coords[a]
        bx, _ = coords[b]
        left_x, right_x = sorted([ax, bx])
        svg.append(line(left_x, ay, right_x, ay, spouse_line_w))

    # 2) 父母-子代连线（child_fams）
    # child_bar_drop 调大 => 蓝圈竖线长、红圈竖线短
    for (fid, mid), children in child_fams.items():
        if fid not in coords or mid not in coords:
            continue
        if not children:
            continue

        fx, fy = coords[fid]
        mx, _ = coords[mid]
        spouse_y = fy
        cx = (fx + mx) / 2
        y_sib = spouse_y + child_bar_drop

        # 夫妻中点到同胞横线（蓝圈那类）
        svg.append(line(cx, spouse_y, cx, y_sib, spouse_line_w))

        valid_children = [cid for cid in children if cid in coords]
        if not valid_children:
            continue

        child_points = [(coords[cid][0], coords[cid][1]) for cid in valid_children]
        xs = sorted([x for x, _ in child_points])

        # 同胞横线
        if len(xs) == 1:
            svg.append(line(cx, y_sib, xs[0], y_sib, spouse_line_w))
        else:
            svg.append(line(xs[0], y_sib, xs[-1], y_sib, spouse_line_w))

        # 同胞横线到孩子图形（红圈那类）
        for px, py in child_points:
            svg.append(line(px, y_sib, px, py - r, spouse_line_w))

    # 3) 标签位置（先算）
    label_positions = compute_label_positions(
        people, coords, base_offset=label_offset, near_x_threshold=115
    )

    # 4) 人物节点
    probands = []
    for p in people:
        pid = p["id"]
        if pid not in coords:
            continue
        x, y = coords[pid]
        sex = p.get("sex", "U")
        affected = bool(p.get("affected", False))
        deceased = bool(p.get("deceased", False))
        proband = bool(p.get("proband", False))
        name = p.get("name", pid)

        if proband:
            probands.append(pid)

        fill = "black" if affected else "white"
        stroke_w = proband_stroke if proband else base_stroke

        if sex == "M":
            svg.append(
                f'<rect x="{x-r}" y="{y-r}" width="{2*r}" height="{2*r}" '
                f'fill="{fill}" stroke="black" stroke-width="{stroke_w}" />'
            )
        elif sex == "F":
            svg.append(
                f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" '
                f'stroke="black" stroke-width="{stroke_w}" />'
            )
        else:
            pts = f"{x},{y-r} {x+r},{y} {x},{y+r} {x-r},{y}"
            svg.append(
                f'<polygon points="{pts}" fill="{fill}" stroke="black" stroke-width="{stroke_w}" />'
            )

        # 死亡斜杠（伸出图形）
        if deceased:
            ex = r + 12
            ey = r + 12
            svg.append(line(x - ex, y + ey, x + ex, y - ey, 3.0))

    # 5) 标签（最后画，避免被线压）
    if show_labels:
        for p in people:
            pid = p["id"]
            if pid not in coords or pid not in label_positions:
                continue
            lx, ly = label_positions[pid]
            svg.append(
                f'<text x="{lx}" y="{ly}" text-anchor="middle" '
                f'font-size="{label_font}" font-family="Arial, Microsoft YaHei">{esc(p.get("name", pid))}</text>'
            )

    # 6) 先证者箭头（短一点）
    used_arrow_tails = []
    for pid in probands:
        x, y = coords[pid]
        ax1, ay1, ax2, ay2 = choose_arrow_anchor(x, y, width, height, used_arrow_tails)
        used_arrow_tails.append((ax1, ay1))
        svg.append(line(ax1, ay1, ax2, ay2, 2.4))

        dx = ax2 - ax1
        dy = ay2 - ay1
        if dx < 0 and dy < 0:
            svg.append(line(ax2, ay2, ax2 + 9, ay2 + 2, 2.4))
            svg.append(line(ax2, ay2, ax2 + 2, ay2 + 9, 2.4))
        elif dx > 0 and dy < 0:
            svg.append(line(ax2, ay2, ax2 - 9, ay2 + 2, 2.4))
            svg.append(line(ax2, ay2, ax2 - 2, ay2 + 9, 2.4))
        elif dx < 0 and dy > 0:
            svg.append(line(ax2, ay2, ax2 + 9, ay2 - 2, 2.4))
            svg.append(line(ax2, ay2, ax2 + 2, ay2 - 9, 2.4))
        else:
            svg.append(line(ax2, ay2, ax2 - 9, ay2 - 2, 2.4))
            svg.append(line(ax2, ay2, ax2 - 2, ay2 - 9, 2.4))

    svg.append("</svg>")
    return "".join(svg)

# =============================
# UI
# =============================
st.title("家系图绘制器（网页填表版｜家庭块布局）")
st.caption("支持 spouse_id（无子代配偶也可显示）、出生顺序、死亡斜杠、患者箭头、儿女/侄子等。")

if "pedigree_df" not in st.session_state:
    st.session_state.pedigree_df = pd.DataFrame(DEFAULT_ROWS)

c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    if st.button("加载示例数据"):
        st.session_state.pedigree_df = pd.DataFrame(DEFAULT_ROWS)
with c2:
    if st.button("清空表格"):
        st.session_state.pedigree_df = pd.DataFrame(columns=[
            "id","name","sex","affected","deceased","father_id","mother_id","spouse_id","proband","birth_order"
        ])
with c3:
    show_labels = st.checkbox("显示姓名标签", value=True)

st.markdown("### 1) 在表格里填写家族成员信息（每行一个人）")

edited_df = st.data_editor(
    st.session_state.pedigree_df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "id": st.column_config.TextColumn("id", help="唯一编号，例如 P1/P2"),
        "name": st.column_config.TextColumn("姓名/称谓", help="如 患者、姐姐、姐夫、妹夫、儿子、侄子"),
        "sex": st.column_config.SelectboxColumn("性别", options=["M", "F", "U"], help="M男 F女 U不明"),
        "affected": st.column_config.CheckboxColumn("患病", help="勾选=实心"),
        "deceased": st.column_config.CheckboxColumn("死亡", help="勾选=斜杠（伸出图形）"),
        "father_id": st.column_config.TextColumn("父亲id", help="填父亲的 id；无可留空"),
        "mother_id": st.column_config.TextColumn("母亲id", help="填母亲的 id；无可留空"),
        "spouse_id": st.column_config.TextColumn("配偶id", help="可选；无子代也建议填（如妹夫/弟媳）"),
        "proband": st.column_config.CheckboxColumn("患者(先证者)", help="只能有一个"),
        "birth_order": st.column_config.NumberColumn(
            "出生顺序",
            help="同一父母下子女排序：1最大，2次大...（左到右）",
            step=1,
            min_value=1
        ),
    },
    key="data_editor_pedigree"
)

graph_title = st.text_input("2) 图标题", value="Pedigree")

if st.button("3) 生成家系图", type="primary"):
    try:
        st.session_state.pedigree_df = edited_df.copy()
        people = df_to_people(edited_df)

        if len(people) == 0:
            st.warning("表格是空的，请先添加至少一位成员。")
        else:
            svg_html = pedigree_to_svg(people, title=graph_title, show_labels=show_labels)

            st.markdown("### 生成结果")
            components.html(svg_html, height=1100, scrolling=True)

            with st.expander("查看当前结构化数据（调试用）", expanded=False):
                st.json(people)

            st.success("已生成家系图（已按你要求调整线长/标签/箭头）。")

    except Exception as e:
        st.error(f"生成失败：{e}")

with st.expander("填写说明（建议第一次看）", expanded=False):
    st.markdown("""
**每一行代表一个人。**

- `id`：唯一编号（例如 `P1`, `P2`）
- `name`：图上显示名称（如“患者”“妹妹”“妹夫”“儿子”）
- `sex`：`M` 男，`F` 女，`U` 不明
- `affected`：勾选=实心（患病）
- `deceased`：勾选=斜杠（死亡）
- `father_id` / `mother_id`：填父母的 `id`（不是名字）
- `spouse_id`：配偶的 `id`（**即使没有孩子也建议填**）
- `proband`：患者/先证者（只能一个）
- `birth_order`：同一父母下子女排序（1最大，左到右）

### 很重要的规则
1. **婚配关系要成对填写**
   - 例如：
   - 妹妹 `spouse_id = P16`
   - 妹夫 `spouse_id = P10`

2. **孩子尽量同时填写 father_id + mother_id**
   - 连线和布局会更稳

### 例子
- 患者 `P1`、配偶 `P11`
  - 儿子：`father_id=P11`, `mother_id=P1`
  - 女儿：`father_id=P11`, `mother_id=P1`

- 姐姐 `P8`、姐夫 `P14`
  - 侄子：`father_id=P14`, `mother_id=P8`

- 妹妹 `P10`、妹夫 `P16`（暂时没孩子也可以）
  - 双方互填 `spouse_id` 即可显示为一对
""")
