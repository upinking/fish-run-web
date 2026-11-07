"""Build the hand-shaped chibi runner used before the Tripo model is ready."""

from math import cos, hypot, pi, sin
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public" / "models" / "runner-preview.glb"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.fps = 30


def material(name, color, roughness=0.46, metallic=0):
    rgb = [int(color[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    rgb = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
    result = bpy.data.materials.new(name)
    result.diffuse_color = (*rgb, 1)
    result.use_nodes = True
    surface = result.node_tree.nodes.get("Principled BSDF")
    surface.inputs["Base Color"].default_value = (*rgb, 1)
    surface.inputs["Roughness"].default_value = roughness
    surface.inputs["Metallic"].default_value = metallic
    return result


hair = material("Cornflower hair", "3E77D8", 0.34)
hair_light = material("Azure hair", "559FEE", 0.32)
hair_dark = material("Blue hair roots", "305CAD", 0.39)
hair_tip = material("Ocean hair tips", "318ADB", 0.34)
navy = material("Ink blue dress", "263D85", 0.58)
dress_blue = material("Navy satin", "3959A8", 0.48)
white = material("Porcelain apron", "F7FCFF", 0.57)
lace = material("Blue white ruffle", "DBEBFA", 0.58)
skin = material("Peach skin", "F7C7B8", 0.61)
cyan = material("Whale fins", "50C1E9", 0.39)
fin_light = material("Whale fin underside", "9BE6F1", 0.44)
shoe = material("Patent shoes", "294C9D", 0.29)
iris = material("Sapphire eyes", "164784", 0.35)
rose = material("Peach cheek", "F29DAD", 0.64)
strand = material("Satin color gradient", "FFFFFF", 0.35)
strand_nodes = strand.node_tree.nodes
strand_color = strand_nodes.new("ShaderNodeVertexColor")
strand_color.layer_name = "Color"
strand.node_tree.links.new(strand_color.outputs["Color"], strand_nodes.get("Principled BSDF").inputs["Base Color"])


def pivot(name, position, parent=None):
    result = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(result)
    result.parent = parent
    result.location = position
    return result


def ellipsoid(name, center, radii, mat, parent, tilt=(0, 0, 0), segments=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=10)
    result = bpy.context.object
    result.name = name
    result.parent = parent
    result.location = center
    result.scale = radii
    result.rotation_euler = tilt
    result.data.materials.append(mat)
    for polygon in result.data.polygons:
        polygon.use_smooth = True
    return result


def mesh(name, vertices, faces, materials, parent):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    result = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(result)
    result.parent = parent
    for mat in materials:
        data.materials.append(mat)
    for face in data.polygons:
        face.use_smooth = True
    return result


def ribbon(name, sections, materials, parent, radial=10, reference=(1, 0, 0)):
    """Sweep changing elliptical sections, with caps and UV-independent color."""
    centers = [Vector(item[0]) for item in sections]
    vertices = []
    for index, (_, wide, deep, _) in enumerate(sections):
        tangent = (centers[min(index + 1, len(centers) - 1)] - centers[max(0, index - 1)]).normalized()
        side = Vector(reference) - tangent * Vector(reference).dot(tangent)
        side.normalize()
        depth = tangent.cross(side).normalized()
        for point in range(radial):
            angle = 2 * pi * point / radial
            vertices.append(centers[index] + wide * cos(angle) * side + deep * sin(angle) * depth)
    faces = [tuple(reversed(range(radial)))]
    for ring in range(len(centers) - 1):
        for point in range(radial):
            following = (point + 1) % radial
            faces.append((ring * radial + point, ring * radial + following,
                          (ring + 1) * radial + following, (ring + 1) * radial + point))
    faces.append(tuple(range((len(centers) - 1) * radial, len(centers) * radial)))
    result = mesh(name, vertices, faces, [strand], parent)
    gradient = result.data.color_attributes.new(name="Color", type="FLOAT_COLOR", domain="POINT")
    for ring, (_, _, _, material_index) in enumerate(sections):
        for point in range(radial):
            gradient.data[ring * radial + point].color = materials[material_index].diffuse_color
    return result


def skirt_shell(name, rings, mat, parent, wave=0.0):
    radial = 40
    vertices = []
    for level, rx, ry in rings:
        for point in range(radial):
            angle = point * 2 * pi / radial
            fold = 1 + wave * cos(angle * 10)
            vertices.append((rx * fold * cos(angle), ry * fold * sin(angle), level))
    faces = []
    for row in range(len(rings) - 1):
        for point in range(radial):
            following = (point + 1) % radial
            faces.append((row * radial + point, (row + 1) * radial + point,
                          (row + 1) * radial + following, row * radial + following))
    faces.append(tuple(reversed(range((len(rings) - 1) * radial, len(rings) * radial))))
    return mesh(name, vertices, faces, [mat], parent)


def consolidate(parent):
    """Keep one mesh per rigid group so the animations stay cheap to draw."""
    parts = [part for part in parent.children if part.type == "MESH"]
    if not parts:
        return
    bpy.ops.object.select_all(action="DESELECT")
    for part in parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    if len(parts) > 1:
        bpy.ops.object.join()
    parts[0].name = parent.name + " mesh"


# glTF's Y-up conversion maps Blender +Y to world -Z, the direction of the run.
root = pivot("RunnerPreview", (0, 0, 0))
bob = pivot("BodyBob", (0, 0, 0), root)
torso = pivot("TorsoLean", (0, 0, 0.65), bob)
head = pivot("Head", (0, 0.03, 0.48), torso)
locks = pivot("BackHair", (0, -0.08, 0.2), head)
tail = pivot("Tail", (0, -0.19, -0.02), torso)

ellipsoid("Bodice", (0, 0.02, 0.11), (0.232, 0.168, 0.194), navy, torso)
ellipsoid("Collar", (0, 0.015, 0.264), (0.145, 0.125, 0.047), white, torso)
ellipsoid("Neck", (0, 0.02, 0.284), (0.096, 0.093, 0.105), skin, torso)
skirt_shell("Pleated skirt", [(0.105, 0.198, 0.151), (0.035, 0.271, 0.204),
            (-0.085, 0.357, 0.263), (-0.145, 0.372, 0.278), (-0.154, 0.351, 0.260)],
            dress_blue, torso, 0.063)
skirt_shell("Underskirt ruffle", [(-0.137, 0.350, 0.260), (-0.172, 0.381, 0.288),
            (-0.191, 0.348, 0.260)], lace, torso, 0.088)
for point in range(18):
    angle = point * 2 * pi / 18
    ellipsoid("Lace scallop", (0.357 * cos(angle), 0.267 * sin(angle), -0.175),
              (0.054, 0.038, 0.022), white, torso, (0, 0, angle + pi / 2), 10)
ellipsoid("Apron panel", (0, 0.223, -0.045), (0.235, 0.069, 0.139), white, torso, (-0.29, 0, 0))
ellipsoid("Sash", (0, 0.007, 0.066), (0.235, 0.177, 0.036), white, torso)
for side in (-1, 1):
    ellipsoid("Apron shoulder strap", (0.125 * side, -0.136, 0.147), (0.037, 0.023, 0.119),
              lace, torso, (0.12, -0.30 * side, 0))
    ellipsoid("Sash bow", (0.125 * side, -0.199, 0.083), (0.127, 0.048, 0.066),
              white, torso, (0, -0.29 * side, 0))
    ellipsoid("Ribbon end", (0.075 * side, -0.206, -0.006), (0.043, 0.031, 0.088),
              lace, torso, (0, -0.39 * side, 0))
ellipsoid("Bow knot", (0, -0.235, 0.081), (0.067, 0.040, 0.049), white, torso)

ellipsoid("Face", (0, 0.048, 0.124), (0.297, 0.248, 0.273), skin, head, segments=24)
ellipsoid("Hair cap", (0, -0.072, 0.187), (0.333, 0.269, 0.288), hair, head, segments=24)
for side in (-1, 1):
    x = side * 0.131
    ellipsoid("Iris", (x, 0.268, 0.129), (0.051, 0.023, 0.059), iris, head)
    ellipsoid("Eye sparkle", (x - 0.015, 0.288, 0.153), (0.014, 0.009, 0.014), white, head, segments=10)
    ellipsoid("Cheek", (side * 0.182, 0.246, 0.064), (0.041, 0.015, 0.017), rose, head, segments=12)
    ribbon("Temple fin", [
        ((0.253 * side, -0.042, 0.127), 0.051, 0.052, 0),
        ((0.331 * side, -0.052, 0.138), 0.063, 0.037, 0),
        ((0.402 * side, -0.064, 0.114), 0.060, 0.023, 1),
        ((0.464 * side, -0.056, 0.133), 0.033, 0.014, 1),
        ((0.500 * side, -0.047, 0.158), 0.003, 0.003, 1),
    ], [cyan, fin_light], head, reference=(0, 0, 1))
    ellipsoid("Side fringe", (0.240 * side, 0.133, 0.206), (0.081, 0.117, 0.194),
              hair, head, (0, -0.16 * side, 0))

ellipsoid("Smile", (0, 0.281, 0.035), (0.035, 0.011, 0.014), rose, head, segments=12)
for point in range(7):
    x = (point - 3) * 0.073
    ellipsoid("Fringe lock", (x, 0.159, 0.271 + abs(x) * 0.19),
              (0.069, 0.122, 0.111), hair if point % 2 else hair_light, head,
              (0.17, -0.22 + point * 0.04, 0))

# The frilled headband remains visible from the rear camera.
for point in range(13):
    angle = point * 2 * pi / 13
    ellipsoid("Maid headband", (0.241 * cos(angle), -0.060 + 0.187 * sin(angle), 0.386),
              (0.066, 0.039, 0.046), white if point % 2 else lace, head,
              (0.22, 0, angle + pi / 2), 12)
ribbon("Ahoge", [
    ((-0.027, -0.050, 0.424), 0.027, 0.023, 0),
    ((-0.056, -0.077, 0.491), 0.025, 0.020, 0),
    ((-0.040, -0.089, 0.538), 0.020, 0.018, 1),
    ((0.007, -0.088, 0.561), 0.014, 0.013, 1),
    ((0.046, -0.084, 0.540), 0.003, 0.004, 1),
], [hair, hair_light], head)

# Layered, tapered locks with different terminal curls read well at small scale.
for index in range(7):
    x = (index - 3) * 0.075
    side = -1 if x < 0 else 1
    center = 1 - abs(x) / 0.225
    length = 0.04 * center + (0.025 if index % 2 else 0)
    ribbon("Back lock", [
        ((x * 0.66, -0.175, 0.174), 0.067, 0.040, 0),
        ((x * 1.07, -0.245, 0.045), 0.083, 0.046, 0),
        ((x * 1.13, -0.236, -0.071), 0.081, 0.052, 1),
        ((x * 1.11, -0.245, -0.190), 0.074, 0.050, 1),
        ((x * 1.13, -0.294, -0.294), 0.061, 0.039, 1),
        ((x * 1.27, -0.350, -0.378 - length), 0.047, 0.028, 2),
        ((x * 1.44, -0.375, -0.409 - length), 0.031, 0.019, 2),
        ((x * 1.48 + 0.025 * side, -0.405, -0.385 - length), 0.004, 0.004, 2),
    ], [hair if index % 2 else hair_dark, hair_light if index % 2 else hair, hair_tip], locks)

ribbon("Whale tail stem", [
    ((0, 0, 0), 0.083, 0.075, 0),
    ((0.083, -0.105, -0.066), 0.087, 0.078, 0),
    ((0.202, -0.203, -0.107), 0.086, 0.067, 0),
    ((0.315, -0.272, -0.112), 0.069, 0.052, 1),
    ((0.424, -0.303, -0.074), 0.055, 0.044, 1),
    ((0.494, -0.315, -0.014), 0.041, 0.035, 1),
], [hair, hair_tip], tail, reference=(0, 0, 1))
ribbon("Upper tail fluke", [
    ((0.462, -0.313, -0.046), 0.048, 0.034, 0),
    ((0.482, -0.321, 0.016), 0.064, 0.039, 0),
    ((0.489, -0.332, 0.090), 0.058, 0.032, 1),
    ((0.470, -0.339, 0.158), 0.035, 0.023, 1),
    ((0.441, -0.350, 0.205), 0.003, 0.003, 1),
], [hair_tip, cyan], tail)
ribbon("Outer tail fluke", [
    ((0.462, -0.313, -0.045), 0.040, 0.030, 0),
    ((0.518, -0.323, -0.027), 0.058, 0.038, 0),
    ((0.573, -0.327, -0.003), 0.062, 0.034, 1),
    ((0.622, -0.338, 0.031), 0.039, 0.022, 1),
    ((0.661, -0.342, 0.084), 0.004, 0.004, 1),
], [hair_tip, cyan], tail, reference=(0, 0, 1))

hips = []
knees = []
arms = []
elbows = []
for side, suffix in [(-1, "L"), (1, "R")]:
    hip = pivot("Leg." + suffix, (0.137 * side, 0.012, 0.541), bob)
    knee = pivot("Knee." + suffix, (0, 0, -0.228), hip)
    arm = pivot("Arm." + suffix, (0.231 * side, 0.01, 0.189), torso)
    elbow = pivot("Elbow." + suffix, (0.067 * side, 0, -0.146), arm)
    hips.append(hip)
    knees.append(knee)
    arms.append(arm)
    elbows.append(elbow)
    ellipsoid("Thigh", (0, 0, -0.109), (0.088, 0.081, 0.146), skin, hip)
    ellipsoid("Calf", (0, 0.003, -0.103), (0.070, 0.071, 0.145), white, knee)
    ellipsoid("Sock cuff", (0, 0, -0.022), (0.083, 0.082, 0.028), lace, knee)
    ellipsoid("Shoe sole", (0, 0.043, -0.283), (0.084, 0.130, 0.024), navy, knee)
    ellipsoid("Blue shoe", (0, 0.044, -0.259), (0.086, 0.128, 0.049), shoe, knee)
    ellipsoid("Shoe strap", (0, 0.020, -0.229), (0.079, 0.039, 0.024), hair_light, knee)
    ellipsoid("Puff sleeve", (0.036 * side, 0, -0.064), (0.090, 0.087, 0.111),
              dress_blue, arm, (0, -0.30 * side, 0))
    ellipsoid("Cuff", (0.064 * side, 0, -0.121), (0.066, 0.066, 0.025), white, arm)
    ellipsoid("Forearm", (0.018 * side, 0.008, -0.064), (0.054, 0.056, 0.084),
              skin, elbow, (0, -0.24 * side, 0))
    ellipsoid("Mitten", (0.033 * side, 0.013, -0.121), (0.053, 0.055, 0.056), skin, elbow)

rig = [bob, torso, head, locks, tail, *hips, *knees, *arms, *elbows]
for group in rig:
    consolidate(group)
rests = {group: (group.location.copy(), group.rotation_euler.copy(), group.scale.copy()) for group in rig}


def reset_pose():
    for group, (location, rotation, scale) in rests.items():
        group.location = location
        group.rotation_euler = rotation
        group.scale = scale


def sole_clearance():
    """Height of the lowest point on the lower shoe, before the body's transform."""
    def sole_bottom(hip, knee):
        thigh = hip.rotation_euler.x
        shin = thigh + knee.rotation_euler.x
        center = hip.location.z - 0.228 * cos(thigh) + 0.043 * sin(shin) - 0.283 * cos(shin)
        radius = hypot(0.130 * sin(shin), 0.024 * cos(shin))
        return center - radius
    return min(sole_bottom(hip, knee) for hip, knee in zip(hips, knees))


def run_pose(t):
    phase = 2 * pi * t
    torso.rotation_euler.x = -0.12 + 0.042 * cos(phase * 2)
    torso.rotation_euler.z = 0.056 * sin(phase)
    head.rotation_euler.x = 0.057
    locks.rotation_euler.x = 0.078 * sin(phase - 0.52)
    locks.rotation_euler.z = -0.08 * sin(phase - 0.52)
    tail.rotation_euler.x = 0.095 * cos(phase - 0.82)
    tail.rotation_euler.z = 0.10 * sin(phase - 0.82)
    for index, (hip, knee, arm, elbow) in enumerate(zip(hips, knees, arms, elbows)):
        stride = sin(phase + index * pi)
        hip.rotation_euler.x = 0.68 * stride + 0.08
        knee.rotation_euler.x = -0.07 - 0.75 * max(0, -stride)
        arm.rotation_euler.x = -0.52 * stride + 0.12
        elbow.rotation_euler.x = 0.62 + 0.18 * stride
    bob.location.z = 0.004 + 0.025 * cos(phase) ** 8 - sole_clearance()


def jump_pose(t):
    tuck = sin(t * pi) ** 1.1
    torso.rotation_euler.x = -0.21 * tuck
    head.rotation_euler.x = 0.15 * tuck
    locks.rotation_euler.x = -0.17 * tuck
    tail.rotation_euler.x = -0.34 * tuck
    for index, (hip, knee, arm, elbow) in enumerate(zip(hips, knees, arms, elbows)):
        hip.rotation_euler.x = (0.77 - 0.32 * index) * tuck
        knee.rotation_euler.x = -(0.91 - 0.25 * index) * tuck
        arm.rotation_euler.x = (0.72 - 0.36 * index) * tuck
        elbow.rotation_euler.x = 0.65 * tuck


def slide_pose(t):
    duck = min(1, t * 10, (1 - t) * 8)
    bob.scale.z = 1 - 0.40 * duck
    torso.rotation_euler.x = -0.73 * duck
    head.rotation_euler.x = 0.29 * duck
    locks.rotation_euler.x = 0.19 * duck
    tail.rotation_euler.x = 0.12 * duck
    for index, (hip, knee, arm, elbow) in enumerate(zip(hips, knees, arms, elbows)):
        hip.rotation_euler.x = (0.89 - 1.15 * index) * duck
        knee.rotation_euler.x = -(0.66 + 0.25 * index) * duck
        arm.rotation_euler.x = (0.47 - 0.22 * index) * duck
        elbow.rotation_euler.x = 0.51 * duck
    bob.location.z = (0.006 - sole_clearance() * bob.scale.z) * duck


def add_clip(name, pose, intervals):
    for group in rig:
        group.animation_data_create()
    for frame in range(intervals + 1):
        reset_pose()
        pose(frame / intervals)
        for group in rig:
            for field in ("location", "rotation_euler", "scale"):
                group.keyframe_insert(data_path=field, frame=frame + 1)
    for group in rig:
        data = group.animation_data
        action = data.action
        action.name = f"{name} {group.name}"
        track = data.nla_tracks.new()
        track.name = name
        track.strips.new(action.name, 1, action)
        data.action = None
        track.mute = True


add_clip("Run", run_pose, 24)
add_clip("Jump", jump_pose, 24)
add_clip("Slide", slide_pose, 24)
reset_pose()
for group in rig:
    for track in group.animation_data.nla_tracks:
        track.mute = False
bpy.context.scene.frame_set(1)

bpy.ops.export_scene.gltf(
    filepath=str(OUTPUT),
    export_format="GLB",
    export_yup=True,
    export_animations=True,
    export_animation_mode="NLA_TRACKS",
    export_merge_animation="NLA_TRACK",
    export_optimize_animation_size=True,
    export_apply=True,
)
print(f"Wrote {OUTPUT}")
