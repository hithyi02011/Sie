import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Pedigree Drawer (Structured Layout)", layout="wide")

# =============================
# 默认示例数据（包含：患者同胞 + 患者子代 + 侄子）
# =============================
DEFAULT_ROWS = [
    # 祖辈（父系 / 母系）
    {"id":"P4","name":"祖父(父系)","sex":"M","affected":True,  "deceased":True,  "father_id":"","mother_id":"","proband":False,"birth_order":None},
    {"id":"P5","name":"祖母(父系)","sex":"F","affected":False, "deceased":False, "father_id":"","mother_id":"","proband":False,"birth_order":None},
    {"id":"P6","name":"外祖父","sex":"M","affected":False, "deceased":False, "father_id":"","mother_id":"","proband":False,"birth_order":None},
    {"id":"P7","name":"外祖母","sex":"F","affected":True,  "deceased":True,  "father_id":"","mother_id":"","proband":False,"birth_order":None},

    # 父母
    {"id":"P2","name":"父亲","sex":"M","affected":False, "deceased":False, "father_id":"P4","mother_id":"P5","proband":False,"birth_order":None},
    {"id":"P3","name":"母亲","sex":"F","affected":False, "deceased":False, "father_id":"P6","mother_id":"P7","proband":False,"birth_order":None},

    # 同胞（按出生顺序）
    {"id":"P8","name":"姐姐","sex":"F","affected":False, "deceased":False, "father_id":"P2","mother_id":"P3","proband":False,"birth_order":1},
    {"id":"P1","name":"患者","sex":"F","affected":True,  "deceased":False, "father_id":"P2","mother_id":"P3","proband":True, "birth_order":2},
    {"id":"P9","name":"弟弟","sex":"M","affected":True,  "deceased":True,  "father_id":"P2","mother_id":"P3","proband":False,"birth_order":3},
    {"id":"P10","name":"妹妹","sex":"F","affected":True, "deceased":True,  "father_id":"P2","mother_id":"P3","proband":False,"birth_order":4},

    # 患者配偶与子代
    {"id":"P11","name":"配偶","sex":"M","affected":False, "deceased":False, "father_id":"","mother_id":"","proband":False,"birth_order":None},
    {"id":"P12","name":"儿子","sex":"M","affected":False, "deceased":False, "father_id":"P11","mother_id":"P1","proband":False,"birth_order":1},
    {"id":"P13","name":"女儿","sex":"F","affected":False, "deceased":False, "father_id":"P11","mother_id":"P1","proband":False,"birth_order":2},

    # 姐姐配偶与侄子
    {"id":"P14","name":"姐夫","sex":"M","affected":False, "deceased":False, "father_id":"","mother_id":"","proband":False,"birth_order":None},
    {"id":"P15","name":"侄子","sex":"M","affected":False, "deceased":False, "father_id":"P14","mother_id":"P8","proband":False,"birth_order":1},
]

# =============================
# DataFrame -> people(list)
# =============================
def to_bool(v):
    if isinstance(v, bool):
        return v
    if pd.isna(v):
        return False
    s = str(v).strip().lower()
    return s in ["true", "1", "yes", "y", "是"]

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

def df_to_people(df: pd.DataFrame):
    rows = []
    for _, r in df.iterrows():
        pid = str(r.get("id", "")).strip()
        if not pid:
            continue

        name = str(r.get("name", "")).strip() or pid
        sex = str(r.get("sex", "U")).strip().upper() or "U"

        father_id = str(r.get("father_id", "")).strip()
        mother_id = str(r.get("mother_id", "")).strip()
        father_id = father_id if father_id else None
        mother_id = mother_id if mother_id else None

        rows.append({
            "id": pid,
            "name": name,
            "sex": sex,
            "affected": to_bool(r.get("affected", False)),
            "deceased": to_bool(r.get("deceased", False)),
            "father_id": father_id,
            "mother_id": mother_id,
            "proband": to_bool(r.get("proband", False)),
            "birth_order": to_int_or_none(r.get("birth_order", None)),
        })
    return rows

# =============================
# 校验
# =============================
def validate_people(people):
    if not isinstance(people, list):
        raise ValueError("输入数据必须是列表。")

    ids = [p.get("id") for p in people]
    if any(i is None or str(i).strip() == "" for i in ids):
        raise ValueError("每个人都必须有 id。")
    if len(ids) != len(set(ids)):
        raise ValueError("存在重复 id，请检查（id 不能重复）。")

    id_set = set(ids)
    for p in people:
        sex = p.get("sex", "U")
        if sex not in ["M", "F", "U"]:
            raise ValueError(f"{p['id']} 的 sex 必须是 M/F/U。")

        for k in ["father_id", "mother_id"]:
            v = p.get(k)
            if v and v not in id_set:
                raise ValueError(f"{p['id']} 的 {k}={v} 不存在（请先添加该人物）。")

    probands = [p["id"] for p in people if p.get("proband")]
    if len(probands) > 1:
        raise ValueError(f"只能有一个患者（proband=True），当前有多个：{probands}")

    # 同父同母子女 birth_order 不重复
    fam_orders = {}
    for p in people:
        fid = p.get("father_id")
        mid = p.get("mother_id")
        bo = p.get("birth_order")
        if fid and mid and bo is not None:
            key = (fid, mid)
            fam_orders.setdefault(key, set())
            if bo in fam_orders[key]:
                raise ValueError(f"同一父母({fid},{mid})下出现重复 birth_order={bo}")
            fam_orders[key].add(bo)

# =============================
# 基础结构工具
# =============================
def compute_generations(people):
    person_map = {p["id"]: p for p in people}
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
        fid = p.get("father_id")
        mid = p.get("mother_id")
        parent_gens = []
        if fid in person_map:
            parent_gens.append(get_gen(fid, visiting))
        if mid in person_map:
            parent_gens.append(get_gen(mid, visiting))

        g = 0 if not parent_gens else max(parent_gens) + 1
        gen[pid] = g
        visiting.remove(pid)
        return g

    for pid in person_map:
        get_gen(pid)
    return gen

def build_families(people):
    """
    返回:
      families[(fid, mid)] = [child_ids...]  （子女已按 birth_order 排）
    注意 key 采用 (father_id, mother_id)
    """
    person_map = {p["id"]: p for p in people}

    def child_sort_key(cid):
        p = person_map[cid]
        bo = p.get("birth_order")
        return (bo is None, bo if bo is not None else 999999, cid)

    families = {}
    for p in people:
        fid = p.get("father_id")
        mid = p.get("mother_id")
        if fid and mid:
            families.setdefault((fid, mid), []).append(p["id"])

    for k in families:
        families[k] = sorted(families[k], key=child_sort_key)
    return families

def find_proband_id(people):
    for p in people:
        if p.get("proband"):
            return p["id"]
    return None

def get_person_map(people):
    return {p["id"]: p for p in people}

# =============================
# 结构化布局（重构版）
# 核心目标：配偶跟着对应人物，不再漂到同代 leftovers 串线
# =============================
def structured_layout(people):
    validate_people(people)
    person_map = get_person_map(people)
    families = build_families(people)
    gen = compute_generations(people)

    # ---- 可调参数（你后面想更松/更紧可以改这里） ----
    x_gap = 150           # 同辈/同胞间距
    y_gap = 220           # 代际间距
    spouse_gap = 90       # 夫妻间距（中心到中心）
    margin_x = 120
    margin_y = 100
    side_block_gap = 180  # 左右块与中心块间距
    child_block_gap = 70  # 下方多个小家庭块之间间距
    # ----------------------------------------------

    coords = {}  # pid -> (x, y)

    proband_id = find_proband_id(people)

    # 若无先证者，就退化为简单代际布局（兜底）
    if not proband_id:
        return fallback_simple_layout(people, families, gen, x_gap, y_gap, margin_x, margin_y)

    proband = person_map[proband_id]
    father_id = proband.get("father_id")
    mother_id = proband.get("mother_id")

    # 核心原生家庭（父母 -> 患者及同胞）
    natal_key = (father_id, mother_id) if (father_id and mother_id) in families else None
    natal_children = families.get((father_id, mother_id), []) if father_id and mother_id else []

    # 画布基准中心
    cx = margin_x + 520
    base_y = margin_y + y_gap  # 父母所在层（中间）
    sib_y = base_y + y_gap     # 患者和同胞层
    parent_parent_y = base_y - y_gap  # 祖辈层
    descendants_y = sib_y + y_gap     # 患者子代/侄子层（只展开到这一层）

    # 1) 放置父母（核心家庭中间）
    if father_id:
        coords[father_id] = (cx - spouse_gap // 2, base_y)
    if mother_id:
        coords[mother_id] = (cx + spouse_gap // 2, base_y)

    # 2) 放置同胞（含患者）按 birth_order，围绕父母中点
    sibling_ids = natal_children[:] if natal_children else [proband_id]
    if proband_id not in sibling_ids:
        sibling_ids.append(proband_id)

    sibling_ids = sorted(sibling_ids, key=lambda pid: (
        person_map[pid].get("birth_order") is None,
        person_map[pid].get("birth_order") if person_map[pid].get("birth_order") is not None else 999999,
        pid
    ))

    if father_id in coords and mother_id in coords:
        sib_center_x = (coords[father_id][0] + coords[mother_id][0]) / 2
    else:
        sib_center_x = cx

    n_sib = len(sibling_ids)
    sib_start_x = sib_center_x - ((n_sib - 1) * x_gap) / 2
    for i, sid in enumerate(sibling_ids):
        coords[sid] = (sib_start_x + i * x_gap, sib_y)

    # 3) 放置父系祖辈家庭（父亲的父母）
    if father_id and father_id in person_map:
        ff = person_map[father_id].get("father_id")
        fm = person_map[father_id].get("mother_id")
        if ff and fm:
            # 放在父亲上方偏左一点
            father_x, _ = coords[father_id]
            coords[ff] = (father_x - side_block_gap // 2, parent_parent_y)
            coords[fm] = (father_x + side_block_gap // 2, parent_parent_y)

            # 如果父亲有同胞（伯叔姑）且你录入了，这里也能放（最多放一层）
            paternal_key = (ff, fm)
            paternal_children = families.get(paternal_key, [])
            if paternal_children:
                # 只给这一层人物定位（父亲同辈），避免与核心父母层冲突
                ccenter = (coords[ff][0] + coords[fm][0]) / 2
                startx = ccenter - ((len(paternal_children)-1) * x_gap) / 2
                for i, cid in enumerate(paternal_children):
                    if cid not in coords:
                        coords[cid] = (startx + i * x_gap, base_y)

    # 4) 放置母系祖辈家庭（母亲的父母）
    if mother_id and mother_id in person_map:
        mf = person_map[mother_id].get("father_id")
        mm = person_map[mother_id].get("mother_id")
        if mf and mm:
            mother_x, _ = coords[mother_id]
            coords[mf] = (mother_x - side_block_gap // 2, parent_parent_y)
            coords[mm] = (mother_x + side_block_gap // 2, parent_parent_y)

            maternal_key = (mf, mm)
            maternal_children = families.get(maternal_key, [])
            if maternal_children:
                ccenter = (coords[mf][0] + coords[mm][0]) / 2
                startx = ccenter - ((len(maternal_children)-1) * x_gap) / 2
                for i, cid in enumerate(maternal_children):
                    if cid not in coords:
                        coords[cid] = (startx + i * x_gap, base_y)

    # 5) 放置“同胞各自家庭”（只展开到下一代：配偶 + 子代）
    #    关键：配偶跟着对应同胞走，防止漂移到祖辈行
    placed_desc_family_blocks = []
    for sid in sibling_ids:
        # 识别这个人作为父或母参与的家庭
        own_family_keys = []
        for (fid, mid), childs in families.items():
            if sid == fid or sid == mid:
                own_family_keys.append((fid, mid))

        if not own_family_keys:
            continue

        # 为简化：一个人只取一个“配偶+子女”家庭（常见场景够用）
        fid, mid = own_family_keys[0]
        children = families[(fid, mid)]

        # 确定这个家庭中的另一方（配偶）
        partner_id = mid if sid == fid else fid
        if sid not in coords:
            continue

        sx, sy = coords[sid]
        # 配偶放在 sid 旁边：默认右侧；若右侧太挤可放左侧（简单策略）
        # 为了避免覆盖相邻同胞，先试右侧，若太近则放左侧
        proposed_right_x = sx + spouse_gap
        too_close = any(abs(proposed_right_x - ox) < 55 and abs(sy - oy) < 5 for pid2, (ox, oy) in coords.items() if pid2 != sid)
        if too_close:
            partner_x = sx - spouse_gap
        else:
            partner_x = proposed_right_x

        partner_y = sy
        coords[partner_id] = (partner_x, partner_y)

        # 该家庭子代摆在 descendants_y 一层，围绕夫妻中点
        center_x = (sx + partner_x) / 2
        n_child = len(children)
        if n_child > 0:
            start_x = center_x - ((n_child - 1) * x_gap) / 2
            for i, cid in enumerate(children):
                coords[cid] = (start_x + i * x_gap, descendants_y)

            placed_desc_family_blocks.append((min(start_x, center_x), max(start_x + (n_child-1)*x_gap if n_child>0 else center_x, center_x)))

    # 6) 放置剩余未定位人物（兜底，按代际分散开；尽量不干扰主结构）
    unplaced = [p["id"] for p in people if p["id"] not in coords]
    if unplaced:
        # 按代分组，放在右下角备用区（不会串到主线）
        gen_to_unplaced = {}
        for pid in unplaced:
            gen_to_unplaced.setdefault(gen.get(pid, 0), []).append(pid)

        reserve_x = cx + 420
        for g in sorted(gen_to_unplaced.keys()):
            y = margin_y + g * y_gap
            x = reserve_x
            for pid in sorted(gen_to_unplaced[g]):
                coords[pid] = (x, y)
                x += x_gap

    # 7) 画布尺寸估算
    max_x = max(x for x, _ in coords.values()) if coords else 1000
    min_x = min(x for x, _ in coords.values()) if coords else 0
    max_y = max(y for _, y in coords.values()) if coords else 700

    # 如果有负坐标（理论上很少），整体右移
    if min_x < 40:
        shift = 50 - min_x
        for pid in list(coords.keys()):
            x, y = coords[pid]
            coords[pid] = (x + shift, y)
        max_x += shift
        min_x += shift

    width = int(max_x + 220)
    height = int(max_y + 240)

    return coords, families, width, height, gen

def fallback_simple_layout(people, families, gen, x_gap, y_gap, margin_x, margin_y):
    coords = {}
    gen_to_ids = {}
    for p in people:
        gen_to_ids.setdefault(gen[p["id"]], []).append(p["id"])
    for g, ids in gen_to_ids.items():
        y = margin_y + g * y_gap
        x = margin_x
        for pid in sorted(ids):
            coords[pid] = (x, y)
            x += x_gap
    max_x = max(x for x, _ in coords.values()) if coords else 1000
    max_y = max(y for _, y in coords.values()) if coords else 700
    width = int(max_x + 200)
    height = int(max_y + 220)
    return coords, families, width, height, gen

# =============================
# SVG 绘制（横平竖直 + 死亡斜杠 + 更远箭头）
# =============================
def line(x1, y1, x2, y2, w=2.5):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="black" stroke-width="{w}" />'

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def choose_arrow_anchor(x, y, width, height, existing_points=None):
    if existing_points is None:
        existing_points = []

    candidates = [
        (x - 120, y - 90, x - 28, y - 22),  # 左上（更远）
        (x + 120, y - 90, x + 28, y - 22),  # 右上
        (x - 120, y + 90, x - 28, y + 22),  # 左下
        (x + 120, y + 90, x + 28, y + 22),  # 右下
    ]

    def score(c):
        tx1, ty1, tx2, ty2 = c
        penalty = 0
        if tx1 < 10 or tx1 > width - 10 or ty1 < 45 or ty1 > height - 10:
            penalty += 1000
        for ex, ey in existing_points:
            d2 = (tx1-ex)**2 + (ty1-ey)**2
            if d2 < 85**2:
                penalty += 300
        if ty1 > y:
            penalty += 20
        return penalty

    return min(candidates, key=score)

def pedigree_to_svg(people, title="Pedigree", show_labels=True):
    validate_people(people)
    coords, families, width, height, gen = structured_layout(people)
    person_map = get_person_map(people)

    # 参数
    r = 26
    base_stroke = 2.6
    proband_stroke = 3.8
    spouse_line_w = 2.4
    label_font = 14
    label_offset = 58

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="background:white">'
    )
    svg.append(
        f'<text x="{width/2}" y="40" text-anchor="middle" font-size="22" '
        f'font-family="Arial, Microsoft YaHei">{esc(title)}</text>'
    )

    # ---- 连线：按家庭画，不会串成一整条 ----
    for (fid, mid), children in families.items():
        if fid not in coords or mid not in coords:
            continue
        fx, fy = coords[fid]
        mx, my = coords[mid]

        # 夫妻线（水平）
        left_x, right_x = sorted([fx, mx])
        spouse_y = fy  # 假设夫妻同层；若数据异常不同层也照当前点画
        svg.append(line(left_x, spouse_y, right_x, spouse_y, spouse_line_w))

        # 子代线（只在有子女时画）
        valid_children = [cid for cid in children if cid in coords]
        if valid_children:
            child_points = [(coords[cid][0], coords[cid][1]) for cid in valid_children]
            cx = (fx + mx) / 2
            y_sib = spouse_y + 50  # 家庭子代横线高度

            # 中轴竖线
            svg.append(line(cx, spouse_y, cx, y_sib, spouse_line_w))

            xs = sorted([x for x, _ in child_points])
            # 单子女也保留短横线更像标准图
            if len(xs) == 1:
                svg.append(line(cx, y_sib, xs[0], y_sib, spouse_line_w))
            else:
                svg.append(line(xs[0], y_sib, xs[-1], y_sib, spouse_line_w))

            # 子女竖线（接到图形上沿）
            for px, py in child_points:
                svg.append(line(px, y_sib, px, py - r, spouse_line_w))

    # ---- 人物图形 ----
    proband_ids = []
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
            proband_ids.append(pid)

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

        if show_labels:
            svg.append(
                f'<text x="{x}" y="{y+label_offset}" text-anchor="middle" '
                f'font-size="{label_font}" font-family="Arial, Microsoft YaHei">{esc(name)}</text>'
            )

    # ---- 先证者箭头（更远）----
    used_arrow_tails = []
    for pid in proband_ids:
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
st.title("家系图绘制器（网页填表版｜结构化布局）")
st.caption("支持：出生顺序、死亡斜杠、先证者箭头；患者后代与侄子等不会再乱串到祖辈主线。")

if "pedigree_df" not in st.session_state:
    st.session_state.pedigree_df = pd.DataFrame(DEFAULT_ROWS)

top1, top2, top3 = st.columns([1, 1, 1])
with top1:
    if st.button("加载示例数据"):
        st.session_state.pedigree_df = pd.DataFrame(DEFAULT_ROWS)
with top2:
    if st.button("清空表格"):
        st.session_state.pedigree_df = pd.DataFrame(
            columns=["id","name","sex","affected","deceased","father_id","mother_id","proband","birth_order"]
        )
with top3:
    show_labels = st.checkbox("显示姓名标签", value=True)

st.markdown("### 1) 在表格里填写家族成员信息（每行一个人）")

edited_df = st.data_editor(
    st.session_state.pedigree_df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "id": st.column_config.TextColumn("id", help="唯一编号，例如 P1/P2"),
        "name": st.column_config.TextColumn("姓名/称谓", help="如 患者、配偶、姐姐、侄子"),
        "sex": st.column_config.SelectboxColumn("性别", options=["M", "F", "U"], help="M男 F女 U不明"),
        "affected": st.column_config.CheckboxColumn("患病", help="勾选=实心"),
        "deceased": st.column_config.CheckboxColumn("死亡", help="勾选=斜杠"),
        "father_id": st.column_config.TextColumn("父亲id", help="填写父亲的 id（不是名字）"),
        "mother_id": st.column_config.TextColumn("母亲id", help="填写母亲的 id（不是名字）"),
        "proband": st.column_config.CheckboxColumn("患者(先证者)", help="只能有一个"),
        "birth_order": st.column_config.NumberColumn(
            "出生顺序",
            help="同一父母下子女排序：1=最大，2=次大，3=更小（左到右）",
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
            components.html(svg_html, height=950, scrolling=True)

            with st.expander("查看当前结构化数据（调试用）", expanded=False):
                st.json(people)

            st.success("已生成家系图（结构化布局版）。")

    except Exception as e:
        st.error(f"生成失败：{e}")

with st.expander("填写说明（建议第一次看）", expanded=False):
    st.markdown("""
**每一行代表一个人。**

- `id`：唯一编号（例如 `P1`, `P2`）
- `name`：显示文字（例如“患者”“父亲”“配偶”“姐夫”“侄子”）
- `sex`：`M` 男，`F` 女，`U` 不明
- `affected`：勾选=实心（患病）
- `deceased`：勾选=斜杠（死亡）
- `father_id` / `mother_id`：填写对应人物的 `id`（不是名字）
- `proband`：患者/先证者（只能一个）
- `birth_order`：同一父母下子女排序（1最大，左到右）

### 加患者子代（儿子/女儿）
假设患者 `P1`、配偶 `P11`：
- 儿子：`father_id=P11`, `mother_id=P1`
- 女儿：`father_id=P11`, `mother_id=P1`

### 加侄子/侄女
假设姐姐 `P8`、姐夫 `P14`：
- 侄子：`father_id=P14`, `mother_id=P8`

> 关键点：每个孩子尽量同时填写 `father_id` 和 `mother_id`，布局会更稳。
""")
