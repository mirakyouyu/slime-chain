# スライムチェイン: 盤面の背景・タイトルロゴ・画面の背景を Blender で作る
# 使い方: blender -b -P tools/render_ui.py -- <出力フォルダ> [board|logo|bg ...]
import bpy, math, sys, os, random
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else "render_out")
WHAT = set(argv[1:]) or {"board", "logo", "bg"}
os.makedirs(OUT, exist_ok=True)
FONT = "/System/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc"

def srgb(h, a=1.0):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c) + (a,)

def reset(w, h, transparent=True):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.film_transparent = transparent
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
    sc.view_settings.view_transform = "Standard"
    try:
        sc.eevee.taa_render_samples = 64
    except Exception:
        pass
    world = bpy.data.worlds.new("W")
    sc.world = world
    world.use_nodes = True
    bgn = world.node_tree.nodes["Background"]
    bgn.inputs[0].default_value = (0.6, 0.65, 0.8, 1)
    bgn.inputs[1].default_value = 0.5
    return sc

def camera(sc, loc, ortho=None, target=(0, 0, 0), lens=50):
    d = bpy.data.cameras.new("Cam")
    if ortho:
        d.type = "ORTHO"
        d.ortho_scale = ortho
    else:
        d.lens = lens
    o = bpy.data.objects.new("Cam", d)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(o)
    sc.camera = o
    return o

def light(sc, kind, loc, energy, size=1.0, color=(1, 1, 1), target=(0, 0, 0)):
    d = bpy.data.lights.new("L", kind)
    d.energy = energy
    d.color = color
    if kind == "AREA":
        d.size = size
    o = bpy.data.objects.new("L", d)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(o)
    return o

def mat(name, rgb, rough=0.3, coat=0.0, emit=None, emit_s=0.0, sss=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = srgb(rgb) if isinstance(rgb, str) else rgb
    p.inputs["Roughness"].default_value = rough
    p.inputs["Coat Weight"].default_value = coat
    p.inputs["Coat Roughness"].default_value = 0.05
    p.inputs["Subsurface Weight"].default_value = sss
    if emit:
        p.inputs["Emission Color"].default_value = srgb(emit)
        p.inputs["Emission Strength"].default_value = emit_s
    return m

def render(sc, name):
    sc.render.filepath = os.path.join(OUT, name)
    bpy.ops.render.render(write_still=True)

# ---------- 盤面の背景(6x12マス・1マス80px) ----------
if "board" in WHAT:
    sc = reset(480, 960, transparent=False)
    sc.world.node_tree.nodes["Background"].inputs[1].default_value = 0.15
    camera(sc, (0, 0, 20), ortho=12)
    # 下地: 溝の色
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
    base = bpy.context.active_object
    base.scale = (6, 12, 1)
    base.data.materials.append(mat("Groove", "#0b0a26", 0.6))
    tile_a = mat("TileA", "#1c1a4a", 0.35, 0.3)
    tile_b = mat("TileB", "#211f55", 0.35, 0.3)
    for y in range(12):
        for x in range(6):
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x - 2.5, 5.5 - y, 0.03))
            t = bpy.context.active_object
            t.scale = (0.9, 0.9, 0.06)
            bv = t.modifiers.new("bv", "BEVEL")
            bv.width = 0.03
            bv.segments = 4
            bv.limit_method = "NONE"
            bpy.ops.object.shade_smooth()
            t.data.materials.append(tile_a if (x + y) % 2 == 0 else tile_b)
    # 上から弱い光・左上からハイライト。下へいくほど少し明るい(底にたまる感じ)
    light(sc, "AREA", (-2, 4, 10), 700, 24, (0.75, 0.75, 1.0))
    light(sc, "AREA", (0, -9, 3), 250, 12, (0.9, 0.6, 1.0))
    render(sc, "board.png")

# ---------- タイトルロゴ ----------
if "logo" in WHAT:
    sc = reset(1400, 380)
    camera(sc, (0, -0.6, 14), ortho=8.6, target=(0, 0.05, 0))
    font = bpy.data.fonts.load(FONT)
    text = "スライムチェイン"
    cols = ["#ff3d5e", "#ff8a1f", "#ffd21f", "#2ee07a", "#3d8bff", "#7a5cff", "#ff4fb3", "#ff3d5e"]
    x = 0.0
    objs = []
    for i, ch in enumerate(text):
        cu = bpy.data.curves.new(f"c{i}", "FONT")
        cu.body = ch
        cu.font = font
        cu.size = 1.25
        cu.extrude = 0.16
        cu.bevel_depth = 0.07
        cu.bevel_resolution = 6
        cu.align_x = "CENTER"
        cu.align_y = "CENTER"
        o = bpy.data.objects.new(f"ch{i}", cu)
        sc.collection.objects.link(o)
        bpy.context.view_layer.update()
        w = o.dimensions.x
        x += w / 2 + (0.02 if i else 0)
        o.location = (x, 0.12 * math.sin(i * 1.3), 0)
        o.rotation_euler = (0, 0, math.radians([4, -5, 3, -4, 5, -3, 4, -2][i]))
        x += w / 2
        o.data.materials.append(mat(f"m{i}", cols[i], 0.22, 1.0, sss=0.2))
        # 黒いふち(後ろに太らせた複製)
        o2 = o.copy()
        o2.data = cu.copy()
        o2.data.bevel_depth = 0.07
        o2.data.offset = 0.085
        o2.data.extrude = 0.05
        o2.location = (o.location.x, o.location.y, -0.2)
        o2.data.materials.clear()
        o2.data.materials.append(mat(f"ol{i}", "#1a1033", 0.5))
        sc.collection.objects.link(o2)
        objs.append(o)
    for o in sc.collection.objects:
        if o.type == "FONT":
            o.location.x -= x / 2
    light(sc, "AREA", (-4, 5, 8), 1500, 5)
    light(sc, "AREA", (5, -4, 5), 400, 8, (0.85, 0.85, 1.0))
    render(sc, "logo.png")

# ---------- 画面の背景(ぼけたスライムが浮かぶ) ----------
if "bg" in WHAT:
    sc = reset(720, 1280, transparent=False)
    w = sc.world.node_tree
    w.nodes["Background"].inputs[0].default_value = srgb("#2a1f6b")
    w.nodes["Background"].inputs[1].default_value = 1.0
    cam = camera(sc, (0, 0, 20), lens=50)
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = 20
    cam.data.dof.aperture_fstop = 0.5
    # 奥の板: 上が紫、下が青緑のグラデーション
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, -30))
    pl = bpy.context.active_object
    pl.scale = (60, 100, 1)
    m = bpy.data.materials.new("Grad")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    rp = nt.nodes.new("ShaderNodeValToRGB")
    rp.color_ramp.elements[0].color = srgb("#1b3f8f")
    rp.color_ramp.elements[1].color = srgb("#5a2a9c")
    rp.color_ramp.elements.new(0.5).color = srgb("#33307f")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs[1].default_value = 1.0
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Y"], rp.inputs[0])
    nt.links.new(rp.outputs[0], em.inputs[0])
    nt.links.new(em.outputs[0], nt.nodes["Material Output"].inputs[0])
    pl.data.materials.append(m)
    random.seed(7)
    cols = ["#ff3d5e", "#2ee07a", "#3d8bff", "#ffd21f"]
    mats = [mat(f"b{i}", c, 0.25, 1.0, sss=0.3) for i, c in enumerate(cols)]
    for i in range(26):
        z = random.uniform(-22, 6)
        sp = (20 - z) * 0.38
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24,
            location=(random.uniform(-sp, sp), random.uniform(-sp * 1.7, sp * 1.7), z))
        o = bpy.context.active_object
        s = random.uniform(0.8, 2.2)
        o.scale = (s, s * 0.92, s * 0.85)
        bpy.ops.object.shade_smooth()
        o.data.materials.append(mats[i % 4])
    light(sc, "AREA", (-10, 14, 22), 6000, 15)
    light(sc, "AREA", (10, -10, 10), 2500, 20, (0.6, 0.7, 1.0))
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 82
    render(sc, "bg.jpg")
print("DONE", WHAT)
