import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Pedigree Drawer (Table Input)", layout="wide")

# =============================
# 默认示例数据（可在网页里直接改）
# 这份顺便示例了“患者晚辈”和“侄子”
# =============================
DEFAULT_ROWS = [
    # 祖辈
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

    # 患者配偶（示例，可删）
    {"id":"P11","name":"配偶","sex":"M","affected":False, "deceased":False, "father_id":"","mother_id":"","proband":False,"birth_order":None},

    # 患者子代（示例：儿子女儿）
    {"id":"P12","name":"儿子","sex":"M","affected":False, "deceased":False, "father_id":"P11","mother_id":"P1","proband":False,"birth_order":1},
    {"id":"P13","name":"女儿","sex":"F","affected":False, "deceased":False, "father_id":"P11","mother_id":"P1","proband":False,"birth_order":2},

    # 姐姐配偶与侄子（示例，可删）
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
            continue  # 跳过空行

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

    # 最多一个先证者
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
# 代际计算
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

# =============================
# 家庭单元（共同父母 -> 子女列表）
# 子女按 birth_order 排
# =============================
def build_families(people):
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

# =============================
# 布局（横平竖直）
# 重点调大代际间距和家庭块间距
# =============================
def layout_people(people):
    gen = compute_generations(people)
    families = build_families(people)

    gen_to_ids = {}
    for p in people:
        gen_to_ids.setdefault(gen[p["id"]], []).append(p["id"])

    # ---- 这里是你想调的“好看程度参数” ----
    x_gap = 145          # 同代人物横向基础间距（加大）
    y_gap = 220          # 代际间距（明显加大）
    margin_x = 90
    margin_y = 95
    family_gap = 130     # 家庭块之间额外间距（加大）
    # ----------------------------------

    coords = {}
    max_gen = max(gen_to_ids.keys()) if gen_to_ids else 0

    for g in range(max_gen + 1):
        y = margin_y + g * y_gap
        x_cursor = margin_x

        fams_this_gen = []
        for (fid, mid), children in families.items():
            if gen.get(fid) == g and gen.get(mid) == g:
                fams_this_gen.append((fid, mid, children))
        fams_this_gen.sort(key=lambda x: (x[0], x[1]))

        placed_in_gen = set()

        for fid, mid, children in fams_this_gen:
            # 父母并排（如果已由别处放置则沿用）
            if fid not in coords:
                coords[fid] = (x_cursor, y)
            if mid not in coords:
                coords[mid] = (x_cursor + x_gap, y)
            placed_in_gen.update([fid, mid])

            # 子女在下一代，以父母中点为中心，按 birth_order 左->右
            child_y = margin_y + (g + 1) * y_gap
            center_x = (coords[fid][0] + coords[mid][0]) / 2
            n = len(children)

            if n > 0:
                start_x = center_x - ((n - 1) * x_gap) / 2
                for i, cid in enumerate(children):
                    if cid not in coords:
                        coords[cid] = (start_x + i * x_gap, child_y)

            block_w = max(2 * x_gap, (max(1, n) - 1) * x_gap + x_gap)
            x_cursor += block_w + family_gap

        # 这一代剩余未放置个体（无配偶记录/孤立）
        leftovers = [pid for pid in sorted(gen_to_ids.get(g, [])) if pid not in placed_in_gen and pid not in coords]
        for pid in leftovers:
            coords[pid] = (x_cursor, y)
            x_cursor += x_gap

    if coords:
        max_x = max(x for x, _ in coords.values())
        max_y = max(y for _, y in coords.values())
    else:
        max_x, max_y = 600, 300

    width = int(max_x + 220)
    height = int(max_y + 260)  # 增大底部留白（方便晚辈标签）
    return coords, families, width, height

# =============================
# SVG绘制
# =============================
def line(x1, y1, x2, y2, w=2.5):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="black" stroke-width="{w}" />'

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def choose_arrow_anchor(x, y, width, height, existing_points=None):
    """
    给先证者找一个更远一点的箭头位置。
    优先左上，再右上，再左下，再右下。
    """
    if existing_points is None:
        existing_points = []

    candidates = [
        # (tail_x, tail_y, tip_x, tip_y)
        (x - 105, y - 85, x - 24, y - 20),  # 左上（更远）
        (x + 105, y - 85, x + 24, y - 20),  # 右上
        (x - 105, y + 85, x - 24, y + 20),  # 左下
        (x + 105, y + 85, x + 24, y + 20),  # 右下
    ]

    def score(c):
        tx1, ty1, tx2, ty2 = c
        penalty = 0
        # 出界惩罚
        if tx1 < 10 or tx1 > width - 10 or ty1 < 45 or ty1 > height - 10:
            penalty += 1000
        # 与已有锚点太近惩罚（简单避重叠）
        for ex, ey in existing_points:
            d2 = (tx1 - ex) ** 2 + (ty1 - ey) ** 2
            if d2 < (70 ** 2):
                penalty += 300
        # 稍微偏好上方
        if ty1 > y:
            penalty += 20
        return penalty

    best = min(candidates, key=score)
    return best

def pedigree_to_svg(people, title="Pedigree", show_labels=True):
    validate_people(people)
    coords, families, width, height = layout_people(people)

    # 图形参数
    r = 26
    base_stroke = 2.6
    proband_stroke = 3.8
    spouse_line_w = 2.4
    label_font = 14
    label_offset = 56  # 标签再往下挪一点，避免贴线

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="background:white">'
    )
    svg.append(
        f'<text x="{width/2}" y="40" text-anchor="middle" font-size="22" '
        f'font-family="Arial, Microsoft YaHei">{esc(title)}</text>'
    )

    # 1) 连线（横平竖直）
    for (fid, mid), children in families.items():
        if fid not in coords or mid not in coords:
            continue
        fx, fy = coords[fid]
        mx, my = coords[mid]

        left_x, right_x = sorted([fx, mx])

        # 夫妻线
        svg.append(line(left_x, fy, right_x, fy, spouse_line_w))

        if children:
            center_x = (fx + mx) / 2
            y_sib = fy + 50  # 子代横线下移一点，视觉更松

            valid_children = [cid for cid in children if cid in coords]
            if not valid_children:
                continue

            child_points = [(coords[cid][0], coords[cid][1]) for cid in valid_children]

            # 中轴竖线
            svg.append(line(center_x, fy, center_x, y_sib, spouse_line_w))

            xs = sorted([x for x, _ in child_points])

            if len(xs) > 1:
                svg.append(line(xs[0], y_sib, xs[-1], y_sib, spouse_line_w))

            # 子女竖线连接到图形上沿
            for cx, cy in child_points:
                if len(xs) == 1 and cx != center_x:
                    svg.append(line(center_x, y_sib, cx, y_sib, spouse_line_w))
                svg.append(line(cx, y_sib, cx, cy - r, spouse_line_w))

    # 2) 人物节点
    proband_ids = []
    for p in people:
        pid = p["id"]
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

        # 标签
        if show_labels:
            svg.append(
                f'<text x="{x}" y="{y+label_offset}" text-anchor="middle" '
                f'font-size="{label_font}" font-family="Arial, Microsoft YaHei">{esc(name)}</text>'
            )

    # 3) 先证者箭头（更远，尽量避免重合）
    used_arrow_tails = []
    for pid in proband_ids:
        x, y = coords[pid]
        ax1, ay1, ax2, ay2 = choose_arrow_anchor(x, y, width, height, existing_points=used_arrow_tails)
        used_arrow_tails.append((ax1, ay1))

        # 箭身
        svg.append(line(ax1, ay1, ax2, ay2, 2.4))

        # 箭头头（根据箭尖方向画 V）
        dx = ax2 - ax1
        dy = ay2 - ay1

        # 简单按象限决定箭头头方向
        if dx < 0 and dy < 0:       # 指向左上
            svg.append(line(ax2, ay2, ax2 + 9, ay2 + 2, 2.4))
            svg.append(line(ax2, ay2, ax2 + 2, ay2 + 9, 2.4))
        elif dx > 0 and dy < 0:     # 指向右上
            svg.append(line(ax2, ay2, ax2 - 9, ay2 + 2, 2.4))
            svg.append(line(ax2, ay2, ax2 - 2, ay2 + 9, 2.4))
        elif dx < 0 and dy > 0:     # 指向左下
            svg.append(line(ax2, ay2, ax2 + 9, ay2 - 2, 2.4))
            svg.append(line(ax2, ay2, ax2 + 2, ay2 - 9, 2.4))
        else:                       # 指向右下
            svg.append(line(ax2, ay2, ax2 - 9, ay2 - 2, 2.4))
            svg.append(line(ax2, ay2, ax2 - 2, ay2 - 9, 2.4))

    svg.append("</svg>")
    return "".join(svg)

# =============================
# UI
# =============================
st.title("家系图绘制器（网页填表版｜纯事实）")
st.caption("支持出生顺序、死亡斜杠、先证者箭头；可继续添加患者子代/侄子等晚辈。")

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
        "id": st.column_config.TextColumn("id", help="唯一编号，不能重复，例如 P1/P2"),
        "name": st.column_config.TextColumn("姓名/称谓", help="如 患者、父亲、母亲、大哥、二姐、儿子、侄子"),
        "sex": st.column_config.SelectboxColumn("性别", options=["M", "F", "U"], help="M男 F女 U不明"),
        "affected": st.column_config.CheckboxColumn("患病", help="勾选=实心；不勾=空心"),
        "deceased": st.column_config.CheckboxColumn("死亡", help="勾选=图形加斜杠"),
        "father_id": st.column_config.TextColumn("父亲id", help="填写父亲的 id（不是名字）"),
        "mother_id": st.column_config.TextColumn("母亲id", help="填写母亲的 id（不是名字）"),
        "proband": st.column_config.CheckboxColumn("患者(先证者)", help="只能有一个；会加粗边框+箭头"),
        "birth_order": st.column_config.NumberColumn(
            "出生顺序",
            help="同一父母下子女排序：1=最大，2=次大，3=更小……（左到右）",
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
            components.html(svg_html, height=900, scrolling=True)

            with st.expander("查看当前结构化数据（调试用）", expanded=False):
                st.json(people)

            st.success("已根据网页表格输入生成家系图。")

    except Exception as e:
        st.error(f"生成失败：{e}")

with st.expander("填写说明（第一次建议看）", expanded=False):
    st.markdown("""
**每一行代表一个人。**

- `id`：唯一编号（例如 `P1`, `P2`）
- `姓名/称谓`：图上显示文字（例如“患者”“父亲”“大哥”“二姐”“儿子”“侄子”）
- `性别`：`M` 男，`F` 女，`U` 不明
- `患病`：勾选=实心；不勾选=空心
- `死亡`：勾选=图形上画斜杠（斜杠会伸出图形外）
- `父亲id` / `母亲id`：填写对应人物的 `id`（不是名字）
- `患者(先证者)`：只能有一个，会加粗边框并画箭头
- `出生顺序`：同一父母下子女排序（`1` 最大、`2` 次大、`3` 更小…），从左到右显示

### 怎么加患者晚辈（儿子/女儿）
假设患者 `id = P1`，配偶 `id = P11`：
- 儿子一行：`father_id = P11`, `mother_id = P1`
- 女儿一行：`father_id = P11`, `mother_id = P1`

### 怎么加侄子/侄女
假设姐姐 `id = P8`，姐夫 `id = P14`：
- 侄子一行：`father_id = P14`, `mother_id = P8`

> 只要父母 ID 填对，程序就会自动放到下一代。  
> 你不填孙辈就不会画孙辈。
""")
