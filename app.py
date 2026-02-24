import json
import math
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Pedigree Drawer (SVG)", layout="wide")

# =============================
# 示例数据（可直接改）
# =============================
DEFAULT_JSON = json.dumps(
    [
        {"id":"P1","name":"患者","sex":"F","affected":True,  "father_id":"P2","mother_id":"P3","proband":True},
        {"id":"P2","name":"父亲","sex":"M","affected":False, "father_id":"P4","mother_id":"P5"},
        {"id":"P3","name":"母亲","sex":"F","affected":False, "father_id":"P6","mother_id":"P7"},
        {"id":"P4","name":"祖父(父系)","sex":"M","affected":True},
        {"id":"P5","name":"祖母(父系)","sex":"F","affected":False},
        {"id":"P6","name":"外祖父","sex":"M","affected":False},
        {"id":"P7","name":"外祖母","sex":"F","affected":True},
        {"id":"P8","name":"姐姐","sex":"F","affected":False, "father_id":"P2","mother_id":"P3"},
        {"id":"P9","name":"弟弟","sex":"M","affected":True,  "father_id":"P2","mother_id":"P3"}
    ],
    ensure_ascii=False,
    indent=2
)

# =============================
# 校验
# =============================
def validate_people(people):
    if not isinstance(people, list):
        raise ValueError("JSON 顶层必须是列表（list）。")
    ids = [p.get("id") for p in people]
    if any(i is None for i in ids):
        raise ValueError("每个人都必须有 id。")
    if len(ids) != len(set(ids)):
        raise ValueError("存在重复 id，请检查。")

    id_set = set(ids)
    for p in people:
        sex = p.get("sex", "U")
        if sex not in ["M", "F", "U"]:
            raise ValueError(f"{p['id']} 的 sex 必须是 'M'/'F'/'U'。")
        for k in ["father_id", "mother_id"]:
            v = p.get(k)
            if v and v not in id_set:
                raise ValueError(f"{p['id']} 的 {k}={v} 不存在于列表中。")

# =============================
# 代际计算（0=最上层）
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
# 构建家庭单元
# key=(father_id,mother_id) -> [child_ids]
# =============================
def build_families(people):
    families = {}
    for p in people:
        fid = p.get("father_id")
        mid = p.get("mother_id")
        if fid and mid:
            families.setdefault((fid, mid), []).append(p["id"])
    return families

# =============================
# 简单布局（横平竖直）
# 思路：
# - 每代一行
# - 每代按“家庭块”分组排
# - 父母并排；子女在下一代同块居中
# =============================
def layout_people(people):
    person_map = {p["id"]: p for p in people}
    gen = compute_generations(people)
    families = build_families(people)

    # 先按代分组
    gen_to_ids = {}
    for p in people:
        gen_to_ids.setdefault(gen[p["id"]], []).append(p["id"])

    # 固定参数（可调）
    x_gap = 120
    y_gap = 160
    margin_x = 60
    margin_y = 70

    coords = {}  # pid -> (x,y), y 是图形中心
    drawn = set()

    max_gen = max(gen_to_ids.keys()) if gen_to_ids else 0

    # 1) 先放置有孩子的父母家庭块（按代）
    for g in range(max_gen + 1):
        y = margin_y + g * y_gap
        x_cursor = margin_x

        # 找这一代作为父母的家庭
        fams_this_gen = []
        for (fid, mid), children in families.items():
            if gen.get(fid) == g and gen.get(mid) == g:
                fams_this_gen.append((fid, mid, children))

        # 为了稳定显示，按父母id排序
        fams_this_gen.sort(key=lambda x: (x[0], x[1]))

        for fid, mid, children in fams_this_gen:
            # 父母位置（并排）
            if fid not in coords:
                coords[fid] = (x_cursor, y)
            if mid not in coords:
                coords[mid] = (x_cursor + x_gap, y)

            drawn.add(fid)
            drawn.add(mid)

            # 子女在下一代，围绕父母中点展开
            child_y = margin_y + (g + 1) * y_gap
            mid_x = (coords[fid][0] + coords[mid][0]) / 2
            n = len(children)
            total_width = (n - 1) * x_gap
            start_x = mid_x - total_width / 2

            for i, cid in enumerate(sorted(children)):
                if cid not in coords:
                    coords[cid] = (start_x + i * x_gap, child_y)
                drawn.add(cid)

            # 给下一个家庭块留空
            block_width = max(2 * x_gap, (len(children) - 1) * x_gap + x_gap)
            x_cursor += block_width + 80

        # 2) 这一代还有没放进去的人（比如祖辈中无配偶记录/单独个体）
        leftovers = [pid for pid in sorted(gen_to_ids.get(g, [])) if pid not in coords]
        for pid in leftovers:
            coords[pid] = (x_cursor, y)
            x_cursor += x_gap

    # 画布尺寸估算
    if coords:
        max_x = max(x for x, _ in coords.values())
        max_y = max(y for _, y in coords.values())
    else:
        max_x, max_y = 600, 300

    width = int(max_x + 120)
    height = int(max_y + 140)

    return coords, gen, families, width, height

# =============================
# SVG 绘制
# =============================
def pedigree_to_svg(people, title="Pedigree Demo", show_labels=True):
    validate_people(people)
    person_map = {p["id"]: p for p in people}
    coords, gen, families, width, height = layout_people(people)

    # 样式参数
    r = 26                # 圆半径/方块半宽
    line_w = 2.5
    label_offset = 42

    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="background:white">')

    # 标题
    safe_title = escape_xml(title)
    svg.append(f'<text x="{width/2}" y="34" text-anchor="middle" font-size="22" font-family="Arial, Microsoft YaHei">{safe_title}</text>')

    # 1) 先画连线（横平竖直）
    for (fid, mid), children in families.items():
        if fid not in coords or mid not in coords:
            continue
        fx, fy = coords[fid]
        mx, my = coords[mid]

        # 夫妻线（水平）
        y_spouse = fy
        x_left = min(fx, mx)
        x_right = max(fx, mx)
        svg.append(line(x_left, y_spouse, x_right, y_spouse, line_w))

        # 子代连接（从夫妻中点往下）
        if children:
            cx = (fx + mx) / 2
            child_points = [(coords[cid][0], coords[cid][1]) for cid in children if cid in coords]
            if child_points:
                child_y = child_points[0][1]
                y_drop = y_spouse + 38  # 从夫妻线往下的水平子代线位置

                # 竖线：夫妻中点 -> 子代水平线
                svg.append(line(cx, y_spouse, cx, y_drop, line_w))

                xs = sorted([x for x, _ in child_points])
                # 子代横线
                if len(xs) >= 2:
                    svg.append(line(xs[0], y_drop, xs[-1], y_drop, line_w))

                # 每个子女竖线（从子代横线到个体）
                for x, y in child_points:
                    svg.append(line(x, y_drop, x, y, line_w))
                # 单个子女时，没有子代横线也无所谓，直接竖线
                if len(xs) == 1:
                    svg.append(line(xs[0], y_drop, xs[0], child_y, line_w))

    # 2) 画人物节点
    for p in people:
        pid = p["id"]
        x, y = coords[pid]
        sex = p.get("sex", "U")
        affected = bool(p.get("affected", False))
        proband = bool(p.get("proband", False))
        name = p.get("name", pid)

        stroke_w = 3.5 if proband else 2.5
        fill = "black" if affected else "white"

        if sex == "M":
            # 方块
            svg.append(
                f'<rect x="{x-r}" y="{y-r}" width="{2*r}" height="{2*r}" '
                f'fill="{fill}" stroke="black" stroke-width="{stroke_w}" />'
            )
        elif sex == "F":
            # 圆圈
            svg.append(
                f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="black" stroke-width="{stroke_w}" />'
            )
        else:
            # 菱形（不明）
            pts = f"{x},{y-r} {x+r},{y} {x},{y+r} {x-r},{y}"
            svg.append(
                f'<polygon points="{pts}" fill="{fill}" stroke="black" stroke-width="{stroke_w}" />'
            )

        if show_labels:
            svg.append(
                f'<text x="{x}" y="{y+label_offset}" text-anchor="middle" '
                f'font-size="14" font-family="Arial, Microsoft YaHei">{escape_xml(name)}</text>'
            )

    svg.append("</svg>")
    return "".join(svg)

def line(x1, y1, x2, y2, w=2):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="black" stroke-width="{w}" />'

def escape_xml(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# =============================
# UI
# =============================
st.title("家系图绘制器（纯事实版｜横平竖直）")
st.caption("只根据事实绘图，不做推理；线条为横线/竖线，不使用斜线。")

with st.expander("JSON 输入格式示例（可直接复制修改）", expanded=False):
    st.code(DEFAULT_JSON, language="json")

json_text = st.text_area(
    "在这里粘贴 / 编辑家族史 JSON",
    value=DEFAULT_JSON,
    height=320
)

c1, c2 = st.columns([1.2, 1])
with c1:
    graph_title = st.text_input("图标题", value="Pedigree Demo")
with c2:
    show_labels = st.checkbox("显示姓名标签", value=True)

if st.button("生成家系图", type="primary"):
    try:
        people = json.loads(json_text)
        svg_html = pedigree_to_svg(people, title=graph_title, show_labels=show_labels)

        st.subheader("生成结果")
        # 用 HTML 直接显示 SVG（比 graphviz_chart 稳）
        components.html(svg_html, height=700, scrolling=True)

        with st.expander("查看 SVG 源码（调试用）", expanded=False):
            st.code(svg_html[:5000] + ("\n..." if len(svg_html) > 5000 else ""), language="html")

        st.success("已根据事实生成家系图（横平竖直版）。")

    except json.JSONDecodeError as e:
        st.error(f"JSON 格式错误：{e}")
    except Exception as e:
        st.error(f"运行失败：{e}")

with st.expander("字段说明", expanded=False):
    st.markdown(
        """
- `id`：唯一编号（不能重复）
- `name`：显示名字（如“父亲”“母亲”“患者”）
- `sex`：`"M"` 男，`"F"` 女，`"U"` 不明
- `affected`：`true`（患病，实心）/ `false`（未患病，空心）
- `father_id`：父亲编号（可选）
- `mother_id`：母亲编号（可选）
- `proband`：是否为患者/先证者（可选，`true` 时边框加粗）
        """
    )
