"""Prepare the project's Hunyuan whale maid for the browser runner.

Run from Blender's Python environment:
  Blender --background --python blender/build_hunyuan_runner.py -- /path/to/hunyuan.glb
The source stays untouched. Pass --output to export to another location.
"""

import argparse
from math import atan2, cos, hypot, pi, sin
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import bmesh
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TRIANGLE_BUDGET = 55_000
RUNNER_HEIGHT = 1.717
TAU = 2 * pi
SKIRT_CENTRE_Y = .008
SKIRT_PANELS = tuple(f"SkirtPanel{index}" for index in range(8))


def load_mesh(source):
    bpy.ops.import_scene.gltf(filepath=str(source), merge_vertices=True)
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if len(meshes) != 1 or any(obj.type == "ARMATURE" for obj in bpy.context.scene.objects):
        raise ValueError("Expected the original unrigged, single-mesh Hunyuan export")
    mesh = meshes[0]

    # Normalize the export to Blender +Y forward, with the soles on the ground.
    # Blender's glTF exporter converts +Y forward to the game's -Z forward.
    aligned = Matrix.Rotation(pi, 4, "Z") @ mesh.matrix_world
    bounds = [aligned @ Vector(corner) for corner in mesh.bound_box]
    bottom = min(point.z for point in bounds)
    scale = RUNNER_HEIGHT / (max(point.z for point in bounds) - bottom)
    mesh.matrix_world = Matrix.Identity(4)
    mesh.data.transform(Matrix.Translation((0, 0, -bottom * scale)) @ Matrix.Scale(scale, 4) @ aligned)
    bpy.context.view_layer.objects.active = mesh

    # Weld co-located glTF vertices so the skin bends continuously at UV seams.
    surface = bmesh.new()
    surface.from_mesh(mesh.data)
    bmesh.ops.remove_doubles(surface, verts=list(surface.verts), dist=.000002)
    surface.to_mesh(mesh.data)
    surface.free()

    simplify = mesh.modifiers.new("Web triangle budget", "DECIMATE")
    simplify.ratio = min(1, TRIANGLE_BUDGET / len(mesh.data.polygons))
    simplify.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=simplify.name)
    return mesh


def resize_textures():
    with TemporaryDirectory(prefix="fishrun-hunyuan-") as directory:
        base_image = None
        for image in list(bpy.data.images):
            is_base = image.name == "texture_pbr_20250901"
            limit = 1536 if is_base else 1024
            if max(image.size) > limit:
                image.scale(limit, limit)
                path = Path(directory) / (image.name + ".png")
                image.filepath_raw = str(path)
                image.file_format = "PNG"
                image.save()

                # Load and pack the new PNG. Repacking a resized imported
                # image can otherwise retain the original embedded PNG.
                resized = bpy.data.images.load(str(path), check_existing=False)
                resized.colorspace_settings.name = image.colorspace_settings.name
                resized.pack()
                image.user_remap(resized)
                bpy.data.images.remove(image)
                image = resized
            if is_base:
                base_image = image
        if base_image is None:
            raise ValueError("The Hunyuan base-colour texture is missing")
        return base_image


def make_rig():
    joints = [
        ("Root", (0, 0, 0), (0, 0, .11), None),
        ("Pelvis", (0, .01, .56), (0, .01, .70), "Root"),
        ("Chest", (0, .01, .69), (0, .025, .995), "Pelvis"),
        ("Head", (0, .025, 1.005), (0, .032, 1.40), "Chest"),
        ("Hair", (0, -.191, 1.249), (0, -.270, .936), "Head"),
        ("Ahoge", (-.03, -.036, 1.53), (-.075, -.025, 1.63), "Head"),
        ("Skirt", (0, SKIRT_CENTRE_Y, .745), (0, 0, .515), "Pelvis"),
        ("Tail", (0, -.12, .68), (0, -.19, .575), "Pelvis"),
        ("TailCurl", (0, -.19, .575), (0, -.29, .488), "Tail"),
        ("TailCurlTip", (0, -.29, .488), (0, -.40, .506), "TailCurl"),
        ("Flukes", (0, -.40, .506), (0, -.52, .595), "TailCurlTip"),
    ]
    for sign, side in [(-1, "L"), (1, "R")]:
        shoulder = (sign * .15, .002, .932)
        elbow = (sign * .266, .009, .80)
        wrist = (sign * .38, .019, .726)
        fingertips = (sign * .445, .024, .684)
        hip = (sign * .115, 0, .566)
        knee = (sign * .126, .011, .338)
        ankle = (sign * .135, -.005, .121)
        toe = (sign * .138, .078, .047)
        joints.extend([
            ("Arm." + side, shoulder, elbow, "Chest"),
            ("Forearm." + side, elbow, wrist, "Arm." + side),
            ("Hand." + side, wrist, fingertips, "Forearm." + side),
            ("Thigh." + side, hip, knee, "Pelvis"),
            ("Shin." + side, knee, ankle, "Thigh." + side),
            ("Foot." + side, ankle, toe, "Shin." + side),
        ])
    rig = bpy.data.objects.new("WhaleMaid", bpy.data.armatures.new("Hunyuan whale maid joints"))
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for name, start, end, parent in joints:
        bone = rig.data.edit_bones.new(name)
        bone.head, bone.tail = start, end
        if parent:
            bone.parent = rig.data.edit_bones[parent]
    for index, name in enumerate(SKIRT_PANELS):
        angle = TAU * index / len(SKIRT_PANELS)
        radial = Vector((cos(angle), sin(angle), 0))
        clockwise_tangent = Vector((sin(angle), -cos(angle), 0))
        centre = Vector((0, SKIRT_CENTRE_Y, 0))
        bone = rig.data.edit_bones.new(name)
        bone.parent = rig.data.edit_bones["Skirt"]
        bone.head = centre + radial * .106 + Vector((0, 0, .722))
        bone.tail = centre + radial * .286 + Vector((0, 0, .532))
        # With X along this tangent, +X bends the hem up and out.
        bone.align_roll(clockwise_tangent.cross(bone.tail - bone.head))
    bpy.ops.object.mode_set(mode="OBJECT")
    return rig, [joint[0] for joint in joints] + list(SKIRT_PANELS)


def ease(amount):
    amount = max(0, min(1, amount))
    return amount * amount * (3 - 2 * amount)


def smooth(start, end, amount):
    return ease((amount - start) / (end - start))


def vertex_colours(mesh, image):
    width, height = image.size
    pixels = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    pixels = pixels.reshape((height, width, 4))
    vertex_ids = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", vertex_ids)
    uv = np.empty(len(mesh.loops) * 2, dtype=np.float32)
    mesh.uv_layers.active.uv.foreach_get("vector", uv)
    uv = uv.reshape((-1, 2))
    columns = np.clip((uv[:, 0] * width).astype(int), 0, width - 1)
    rows = np.clip((uv[:, 1] * height).astype(int), 0, height - 1)
    colours = np.zeros((len(mesh.vertices), 3))
    np.add.at(colours, vertex_ids, pixels[rows, columns, :3])
    counts = np.bincount(vertex_ids, minlength=len(colours))
    return colours / np.maximum(counts[:, None], 1)


def paint_weights(mesh, image, names):
    bone_index = {name: index for index, name in enumerate(names)}
    points = np.array([vertex.co[:] for vertex in mesh.vertices])
    colours = vertex_colours(mesh, image)
    weights = np.zeros((len(points), len(names)))
    for row, (x, y, z) in enumerate(points):
        side = ".L" if x < 0 else ".R"
        distance_from_centre = abs(x)
        red, _, blue = colours[row]
        skin = smooth(.025, .095, red - blue)

        # Blue and white folds overlap the limbs in space. The base colour
        # helps separate skin from the garment before smoothing along the mesh.
        tail = smooth(-.23, -.36, y) * smooth(.86, .755, z)
        curl = smooth(-.23, -.38, y)
        fluke = smooth(-.36, -.49, y)
        weights[row, bone_index["Tail"]] = tail * (1 - curl)
        weights[row, bone_index["TailCurl"]] = tail * curl * (1 - fluke)
        weights[row, bone_index["Flukes"]] = tail * curl * fluke
        torso = 1 - tail

        arm_span = smooth(.176, .306, distance_from_centre)
        arm_height = smooth(.65, .72, z) * smooth(1.015, .94, z)
        arm_depth = smooth(-.17, -.055, y)
        sleeve_line = .932 - .86 * (distance_from_centre - .15)
        sleeve = smooth(.36, .205, distance_from_centre) * smooth(.105, .045, abs(z - sleeve_line))
        arm = arm_span * arm_height * arm_depth * max(skin, sleeve)
        hand = smooth(.34, .421, distance_from_centre)
        forearm = smooth(.212, .315, distance_from_centre)
        weights[row, bone_index["Hand" + side]] = torso * arm * hand
        weights[row, bone_index["Forearm" + side]] = torso * arm * (1 - hand) * forearm
        weights[row, bone_index["Arm" + side]] = torso * arm * (1 - hand) * (1 - forearm)
        torso *= 1 - arm

        head = max(smooth(.94, 1.065, z), smooth(.77, .93, z) * smooth(-.042, -.17, y))
        ahoge = smooth(1.51, 1.605, z)
        weights[row, bone_index["Head"]] = torso * head * (1 - ahoge)
        weights[row, bone_index["Ahoge"]] = torso * head * ahoge
        torso *= 1 - head

        leg = smooth(.59, .47, z) * smooth(-.28, -.155, y) * max(skin, smooth(.46, .38, z))
        foot = smooth(.15, .085, z)
        shin = smooth(.40, .29, z)
        weights[row, bone_index["Foot" + side]] = torso * leg * foot
        weights[row, bone_index["Shin" + side]] = torso * leg * (1 - foot) * shin
        weights[row, bone_index["Thigh" + side]] = torso * leg * (1 - foot) * (1 - shin)
        torso *= 1 - leg

        skirt = smooth(.77, .65, z)
        weights[row, bone_index["Skirt"]] = torso * skirt
        weights[row, bone_index["Chest"]] = torso * (1 - skirt)

    # Diffuse across mesh edges, then retain glTF's four strongest influences.
    edges = np.array([edge.vertices[:] for edge in mesh.edges], dtype=np.int32)
    origins = np.r_[edges[:, 0], edges[:, 1]]
    neighbours = np.r_[edges[:, 1], edges[:, 0]]
    edge_weights = 1 / np.maximum(.002, np.linalg.norm(points[neighbours] - points[origins], axis=1))
    totals = np.bincount(origins, weights=edge_weights, minlength=len(points))
    for _ in range(10):
        average = np.zeros_like(weights)
        np.add.at(average, origins, weights[neighbours] * edge_weights[:, None])
        weights = np.where(totals[:, None] > 0, .5 * (weights + average / np.maximum(totals[:, None], 1)), weights)
    strongest = np.argpartition(weights, -4, axis=1)[:, -4:]
    packed = np.zeros_like(weights)
    np.put_along_axis(packed, strongest, np.take_along_axis(weights, strongest, axis=1), axis=1)
    return packed / packed.sum(axis=1, keepdims=True)


def split_skirt_weights(mesh, weights, skirt_index):
    panel_count = len(SKIRT_PANELS)
    body_count = weights.shape[1]
    weights = np.pad(np.where(weights > .0005, weights, 0), ((0, 0), (0, panel_count)))
    for vertex, influences in zip(mesh.vertices, weights):
        skirt_weight = influences[skirt_index]
        available_slots = 5 - np.count_nonzero(influences)
        if skirt_weight == 0 or available_slots < 2:
            continue
        x, y, z = vertex.co
        y -= SKIRT_CENTRE_Y
        # Keep the waist and the inner hip seam pinned to the original bone.
        flex = smooth(.719, .546, z) * smooth(.135, .235, hypot(x, y)) * smooth(.435, .510, z)
        if flex == 0:
            continue
        position = (atan2(y, x) * panel_count / TAU) % panel_count
        sector = int(position)
        next_share = ease(position - sector)
        splits = [
            (skirt_index, 1 - flex),
            (body_count + sector % panel_count, flex * (1 - next_share)),
            (body_count + (sector + 1) % panel_count, flex * next_share),
        ]
        # Conserve the original skirt influence while staying within glTF's
        # four slots. The pelvis, tail and leg weights keep their exact shares.
        chosen = sorted(splits, key=lambda pair: pair[1], reverse=True)[:available_slots]
        total = sum(share for _, share in chosen)
        influences[skirt_index] = 0
        for joint, share in chosen:
            influences[joint] = skirt_weight * share / total
    return weights


def bind_mesh(mesh, rig, names, image):
    body_names = names[:-len(SKIRT_PANELS)]
    body_weights = paint_weights(mesh.data, image, body_names)
    weights = split_skirt_weights(mesh.data, body_weights, body_names.index("Skirt"))
    mesh.name = "Hunyuan whale maid"
    mesh.parent = rig
    groups = [mesh.vertex_groups.new(name=name) for name in names]
    for vertex, joint in zip(*np.nonzero(weights)):
        groups[joint].add([int(vertex)], float(weights[vertex, joint]), "REPLACE")
    modifier = mesh.modifiers.new("Fitted whale maid skeleton", "ARMATURE")
    modifier.object = rig
    dominant = body_weights.argmax(axis=1)
    return [
        (vertex.co.copy(), names[joint])
        for vertex, joint in zip(mesh.data.vertices, dominant)
        if vertex.co.z < .07 and names[joint].startswith("Foot.")
    ]


def animate(mesh, rig, soles):
    poses = rig.pose.bones
    rest = {bone.name: bone.matrix_local for bone in rig.data.bones}
    axes = {name: matrix.to_quaternion() for name, matrix in rest.items()}

    def rotate(name, x=0, y=0, z=0):
        axis = axes[name]
        poses[name].rotation_quaternion = axis.inverted() @ Euler((x, y, z)).to_quaternion() @ axis

    def set_root_height(height):
        poses["Root"].location = axes["Root"].inverted() @ Vector((0, 0, height))

    def ground_feet(offset):
        bpy.context.view_layer.update()
        foot_matrices = {name: poses[name].matrix @ rest[name].inverted() for name in ("Foot.L", "Foot.R")}
        set_root_height(offset - min((foot_matrices[name] @ point).z for point, name in soles))

    def run(t):
        phase = TAU * t
        rotate("Pelvis", z=.065 * sin(phase))
        rotate("Chest", x=-.15, z=-.12 * sin(phase))
        rotate("Head", x=.073, z=.035 * sin(phase))
        rotate("Hair", x=.062 * cos(phase * 2 - .6), z=.091 * sin(phase - .52))
        rotate("Skirt", x=-.054 + .04 * cos(phase * 2), y=.053 * sin(phase))
        rotate("Tail", x=.12 * cos(phase * 2 - .66), z=.17 * sin(phase - .76))
        rotate("Flukes", x=.20 * cos(phase * 2 - 1.2), z=.11 * sin(phase - 1.2))
        for index, side in enumerate((".L", ".R")):
            sign = 2 * index - 1
            stride = sin(phase + index * pi)
            lift = max(0, cos(phase + index * pi))
            rotate("Thigh" + side, x=.61 * stride + .04)
            rotate("Shin" + side, x=-.12 - .95 * lift)
            rotate("Foot" + side, x=.28 * lift - .16 * stride)
            rotate("Arm" + side, x=-.66 * stride, y=sign * .50)
            rotate("Forearm" + side, x=.95 + .16 * stride)
            rotate("Hand" + side, y=-sign * .08)
        ground_feet(.004 + .018 * cos(phase * 2) ** 4)

    def jump(t):
        tuck = sin(pi * t) ** 1.15
        rotate("Chest", x=-.27 * tuck)
        rotate("Head", x=.19 * tuck)
        rotate("Hair", x=-.20 * tuck)
        rotate("Skirt", x=-.11 * tuck)
        rotate("Tail", x=-.29 * tuck)
        rotate("Flukes", x=-.22 * tuck)
        for index, side in enumerate((".L", ".R")):
            sign = 2 * index - 1
            rotate("Thigh" + side, x=(.95 - .47 * index) * tuck)
            rotate("Shin" + side, x=-(1.20 - .36 * index) * tuck)
            rotate("Foot" + side, x=.21 * tuck)
            rotate("Arm" + side, x=(.82 - .26 * index) * tuck, y=sign * (.34 - .18 * tuck))
            rotate("Forearm" + side, x=.48 * tuck)

    def roll(t):
        tuck = ease(t / .18) * ease((1 - t) / .18)
        turn = ease((t - .08) / .82)
        rotate("Pelvis", x=-TAU * turn)
        poses["Root"].scale.y = 1 - .26 * tuck
        rotate("Chest", x=-1.52 * tuck)
        rotate("Head", x=-.39 * tuck)
        rotate("Ahoge", x=-.77 * tuck)
        rotate("Skirt", x=.10 * tuck)
        rotate("Tail", x=-1.17 * tuck)
        rotate("TailCurl", x=-.71 * tuck)
        rotate("Flukes", x=-.35 * tuck)
        for sign, side in [(-1, ".L"), (1, ".R")]:
            rotate("Thigh" + side, x=1.69 * tuck, y=.16 * sign * tuck)
            rotate("Shin" + side, x=-1.99 * tuck)
            rotate("Foot" + side, x=.35 * tuck)
            rotate("Arm" + side, x=.80 * tuck, y=.79 * sign * tuck)
            rotate("Forearm" + side, x=.96 * tuck)

        # Use the deformed mesh's lowest point as the floor contact. Squash
        # lightly at the tightest point to fit underneath the 0.94 m bar.
        bpy.context.view_layer.update()
        evaluated = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
        surface = evaluated.to_mesh()
        heights = [vertex.co.z for vertex in surface.vertices]
        evaluated.to_mesh_clear()
        bottom = min(heights)
        height_limit = .902 + (1.738 - .902) * (1 - tuck)
        correction = min(1, height_limit / (max(heights) - bottom))
        poses["Root"].scale.y *= correction
        set_root_height(.014 - bottom * correction)

    def boost(t):
        flight = ease(t / .11) * ease((1 - t) / .12)
        launch = sin(pi * ease(t / .17))
        wave = TAU * 5 * t
        sway = flight * sin(wave)

        # Pitch forward after a quick sweep, then soften back into the run.
        # The game moves the model upward, so the root stays in place.
        rotate("Pelvis", x=-.18 * flight - .08 * launch, z=.035 * sway)
        rotate("Chest", x=-.47 * flight + .12 * launch, z=-.06 * sway)
        rotate("Head", x=.29 * flight, z=.04 * sway)
        rotate("Hair", x=flight * (.05 + .065 * cos(wave - .45)), z=.09 * sway)
        rotate("Ahoge", x=flight * (.10 + .16 * cos(wave - .85)), z=.10 * sway)
        rotate("Skirt", x=-.10 * flight)
        rotate("Tail", x=flight * (-.18 + .10 * cos(wave - .5)), z=.13 * sway)
        rotate("TailCurl", x=.12 * flight * cos(wave - .9), z=.09 * flight * sin(wave - .5))
        rotate("Flukes", x=.19 * flight * cos(wave - 1.3), z=.12 * flight * sin(wave - .9))
        for sign, side in [(-1, ".L"), (1, ".R")]:
            counter = sign * .065 * sway
            rotate("Thigh" + side, x=.25 * flight + .51 * launch + counter)
            rotate("Shin" + side, x=-.58 * flight - .39 * launch - counter)
            rotate("Foot" + side, x=.19 * flight)
            rotate("Arm" + side, x=-.37 * flight + .48 * launch + counter, y=-sign * .31 * flight)
            rotate("Forearm" + side, x=.21 * flight + .43 * launch)
            rotate("Hand" + side, y=sign * .08 * flight)

    def reset_pose():
        for joint in poses:
            joint.rotation_mode = "QUATERNION"
            joint.rotation_quaternion = Quaternion()
            joint.location = (0, 0, 0)
            joint.scale = (1, 1, 1)

    for name, movement, frames in [
        ("Run", run, 25),
        ("Jump", jump, 25),
        ("Roll", roll, 25),
        ("Boost", boost, 150),
    ]:
        for frame in range(frames):
            reset_pose()
            movement(frame / (frames - 1))
            for joint in poses:
                if not joint.name.startswith("SkirtPanel"):
                    joint.keyframe_insert(data_path="rotation_quaternion", frame=frame + 1, group=joint.name)
            for channel in ("location", "scale"):
                poses["Root"].keyframe_insert(data_path=channel, frame=frame + 1, group="Root")
        action = rig.animation_data.action
        action.name = name
        track = rig.animation_data.nla_tracks.new()
        track.name = name
        track.strips.new(name, 1, action)
        rig.animation_data.action = None
        track.mute = True

    reset_pose()
    for track in rig.animation_data.nla_tracks:
        track.mute = False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "public/models/runner-hunyuan.glb")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if args.source.resolve() == args.output.resolve():
        parser.error("The output must differ from the original Hunyuan file")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 30

    mesh = load_mesh(args.source)
    image = resize_textures()
    rig, names = make_rig()
    soles = bind_mesh(mesh, rig, names, image)
    animate(mesh, rig, soles)
    scene.frame_set(1)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(args.output), export_format="GLB",
        export_animations=True, export_animation_mode="NLA_TRACKS",
        export_merge_animation="NLA_TRACK", export_optimize_animation_size=True,
        export_rest_position_armature=True,
    )
    mesh.data.calc_loop_triangles()
    print(f"Wrote {args.output} with {len(mesh.data.loop_triangles):,} triangles and {len(names)} joints")


if __name__ == "__main__":
    main()
