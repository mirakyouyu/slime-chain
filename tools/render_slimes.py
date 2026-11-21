# スライムチェイン: スライムのスプライトを Blender で作る
# 使い方: blender -b -P tools/render_slimes.py -- <出力フォルダ> [test]
# 1マス=1.0 の正射影カメラでマス目ぴったりに撮る。つながる方向にはとなりの玉と橋の玉も置くので、
# となりのスプライトと並べると境目がつながって見える。
import bpy, math, sys, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else "render_out")
TEST = len(argv) > 1 and argv[1] == "test"
PX = 160  # 1マスの画素数
os.makedirs(OUT, exist_ok=True)

# 色(sRGB 16進) : 本体 / 影側
COLORS = {
    1: ("#ff3d5e", "#b5122f"),  # あか
    2: ("#2ee07a", "#0f8a44"),  # みどり
    3: ("#3d8bff", "#1240b0"),  # あお
    4: ("#ffd21f", "#d98a00"),  # きいろ
    5: ("#c9d3e6", "#7d86a0"),  # おじゃま
}
DIRS = [(0, 1), (1, 0), (0, -1), (-1, 0)]  # 上 右 下 左(ビット 1 2 4 8)

def srgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c) + (1.0,)

# ---------- シーン ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x = sc.render.resolution_y = PX
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA"
sc.view_settings.view_transform = "Standard"
sc.view_settings.look = "None"
try:
    sc.eevee.taa_render_samples = 64
except Exception:
    pass

world = bpy.data.worlds.new("W")
sc.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.55, 0.6, 0.75, 1)
bg.inputs[1].default_value = 0.55

cam_d = bpy.data.cameras.new("Cam")
cam_d.type = "ORTHO"
cam_d.ortho_scale = 1.0
cam = bpy.data.objects.new("Cam", cam_d)
cam.location = (0, 0, 10)
sc.collection.objects.link(cam)
sc.camera = cam

def light(name, kind, loc, energy, size=1.0, color=(1, 1, 1)):
    d = bpy.data.lights.new(name, kind)
    d.energy = energy
    d.color = color
    if kind == "AREA":
        d.size = size
    o = bpy.data.objects.new(name, d)
    o.location = loc
    sc.collection.objects.link(o)
    o.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return o

light("Key", "AREA", (-2.2, 2.6, 4.0), 180, 1.2)          # 左上からの主光(ハイライト)
light("Fill", "AREA", (2.5, -1.0, 3.0), 40, 3.0, (0.8, 0.85, 1.0))
light("Rim", "AREA", (1.5, -2.5, -0.5), 60, 2.0, (1.0, 0.95, 0.9))

# ---------- マテリアル ----------
def body_mat(c):
    base, shade = COLORS[c]
    m = bpy.data.materials.new(f"Body{c}")
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    # 正面ほど明るく、ふちほど濃い色(ぷるっとした厚み)
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.45
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = srgb(base)
    ramp.color_ramp.elements[1].color = srgb(shade)
    ramp.color_ramp.elements[1].position = 0.9
    nt.links.new(lw.outputs["Facing"], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = 0.32
    p.inputs["Coat Weight"].default_value = 1.0
    p.inputs["Coat Roughness"].default_value = 0.06
    p.inputs["Subsurface Weight"].default_value = 0.25
    p.inputs["Subsurface Radius"].default_value = (0.3, 0.3, 0.3)
    p.inputs["Subsurface Scale"].default_value = 0.1
    if c == 5:
        p.inputs["Roughness"].default_value = 0.45
        p.inputs["Coat Weight"].default_value = 0.4
    return m

def flat_mat(name, rgb, rough=0.2, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = srgb(rgb)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Coat Weight"].default_value = coat
    return m

EYE_W = flat_mat("EyeWhite", "#ffffff", 0.35, 0.5)
EYE_B = flat_mat("Pupil", "#1d1630", 0.15, 1.0)
EYE_HI = bpy.data.materials.new("Catch")
EYE_HI.use_nodes = True
_n = EYE_HI.node_tree.nodes
_e = _n.new("ShaderNodeEmission")
_e.inputs[1].default_value = 4.0
EYE_HI.node_tree.links.new(_e.outputs[0], _n["Material Output"].inputs[0])

BODY = {c: body_mat(c) for c in COLORS}

# ---------- 形 ----------
R = 0.8          # 玉の半径(メタボール。見た目の半径は約0.46)
BRIDGE = 0.0     # 橋の玉の大きさ(0で無し)
ZS = 0.82        # 奥行きをすこしつぶす(正面から見たときの立体感用)
THRESH = 0.6

def clear_scene():
    for o in list(sc.collection.objects):
        if o.type in ("META", "MESH"):
            bpy.data.objects.remove(o, do_unlink=True)

def make_body(c, mask, squash=1.0):
    mb = bpy.data.metaballs.new("MB")
    mb.resolution = 0.025  # 0.5で割り切れる値(境目の形を左右でそろえる)
    mb.render_resolution = 0.0125
    mb.threshold = THRESH
    def ball(x, y, r):
        e = mb.elements.new()
        e.co = (x, y, 0)
        e.radius = r
        e.stiffness = 2.0
    ball(0, 0, R)
    for b, (dx, dy) in enumerate(DIRS):
        if mask & (1 << b):
            ball(dx, dy, R)                       # となりの玉
            if BRIDGE: ball(dx * 0.5, dy * 0.5, R * BRIDGE)  # 橋(くびれ)
    o = bpy.data.objects.new("Body", mb)
    o.scale = (1, squash, ZS)
    sc.collection.objects.link(o)
    o.data.materials.append(BODY[c])
    return o

def ellipsoid(name, loc, scale, mat, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    bpy.ops.object.shade_smooth()
    o.data.materials.append(mat)
    return o

def surf_z(x, y, r=0.46):
    return ZS * math.sqrt(max(0.0, r * r - x * x - y * y))

def make_face(kind):
    """kind: normal / pop(にっこり) / garbage"""
    for s in (-1, 1):
        ex, ey = s * 0.17, 0.05
        z = surf_z(ex, ey)
        tilt = (-ey * 1.6, s * ex * 1.8, 0)
        if kind == "pop":
            # にっこり目: 細いアーチ(つぶした輪っか)
            bpy.ops.mesh.primitive_torus_add(major_radius=0.09, minor_radius=0.024, location=(ex, ey - 0.02, z + 0.005))
            t = bpy.context.active_object
            t.scale = (1, 1, 0.6)
            bpy.ops.object.shade_smooth()
            t.data.materials.append(EYE_B)
            # 下半分を隠すため本体色の板は使わず、ブーリアンで下を消す
            cut = bpy.data.objects.new("cut", None)
            bpy.ops.mesh.primitive_cube_add(size=0.2, location=(ex, ey - 0.12, z))
            cb = bpy.context.active_object
            mod = t.modifiers.new("b", "BOOLEAN")
            mod.operation = "DIFFERENCE"
            mod.object = cb
            bpy.context.view_layer.objects.active = t
            bpy.ops.object.modifier_apply(modifier="b")
            bpy.data.objects.remove(cb, do_unlink=True)
            continue
        if kind == "garbage":
            ellipsoid("Eye", (ex, ey, z + 0.01), (0.05, 0.065, 0.025), EYE_B, tilt)
            continue
        ellipsoid("Eye", (ex, ey, z - 0.01), (0.115, 0.145, 0.06), EYE_W, tilt)
        px, py = ex + s * 0.015, ey - 0.025
        ellipsoid("Pupil", (px, py, surf_z(px, py) + 0.03), (0.072, 0.094, 0.035), EYE_B, tilt)
        ellipsoid("Hi", (px - 0.026, py + 0.04, surf_z(px, py) + 0.06), (0.024, 0.027, 0.012), EYE_HI)
        ellipsoid("Hi2", (px + 0.028, py - 0.04, surf_z(px, py) + 0.06), (0.011, 0.011, 0.007), EYE_HI)

def render(path):
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)

jobs = []
for c in (1, 2, 3, 4):
    for mask in range(16):
        jobs.append((c, mask, "normal", f"s{c}_{mask:02d}.png"))
    jobs.append((c, 0, "pop", f"s{c}_pop.png"))
jobs.append((5, 0, "garbage", "s5_00.png"))
if TEST:
    jobs = [j for j in jobs if j[0] == 1 and j[1] in (0, 2, 8, 10, 5, 15, 1, 4)] + [j for j in jobs if j[2] in ("pop", "garbage")]

for c, mask, kind, name in jobs:
    clear_scene()
    make_body(c, mask)
    make_face(kind)
    render(os.path.join(OUT, name))
print("DONE", len(jobs))
