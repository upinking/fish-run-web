"""Build the skinned 3D whale maid from the front, side and back reference views.

Run Blender in background with --python blender/build_whale_maid.py.
Add -- --render to save eight studio previews in output.
The rig uses Blender +Y forward and glTF -Z forward.
"""

from math import cos, pi, sin, sqrt
from pathlib import Path
import sys

import bpy
from mathutils import Euler, Quaternion, Vector


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public/models/runner-whale-maid.glb"
TAU = 2 * pi

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = 30


def rgba(hex_color):
    srgb = [int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return (*[v / 12.92 if v < .04045 else ((v + .055) / 1.055) ** 2.4 for v in srgb], 1)


def mix_color(a, b, t):
    return tuple(u + (v - u) * t for u, v in zip(a, b))


def material(name, color, roughness=.45, *, vertex=False, texture=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = rgba(color)
    nodes = mat.node_tree.nodes
    shader = nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = mat.diffuse_color
    shader.inputs["Roughness"].default_value = roughness
    if vertex:
        paint = nodes.new("ShaderNodeVertexColor")
        paint.layer_name = "Paint"
        mat.node_tree.links.new(paint.outputs["Color"], shader.inputs["Base Color"])
    if texture:
        paint = nodes.new("ShaderNodeTexImage")
        paint.image = texture
        mat.node_tree.links.new(paint.outputs["Color"], shader.inputs["Base Color"])
    return mat


def painted_image(name, size, paint):
    image = bpy.data.images.new(name, width=size, height=size, alpha=False)
    pixels = []
    for row in range(size):
        for column in range(size):
            pixels.extend(paint((column + .5) / size, (row + .5) / size))
    image.pixels.foreach_set(pixels)
    image.pack()
    return image


def iris_paint(u, v):
    x, y = 2 * u - 1, 2 * v - 1
    r = sqrt(x * x + y * y)
    light = max(0, min(1, .8 - y * .65))
    blue = mix_color((.025, .11, .28, 1), (.13, .62, .93, 1), light)
    rim = max(0, min(1, (r - .77) * 8))
    blue = mix_color(blue, (.025, .10, .24, 1), rim)
    pupil = sqrt((x / .64) ** 2 + ((y - .09) / .66) ** 2)
    if pupil < 1:
        blue = mix_color((.017, .032, .09, 1), blue, max(0, (pupil - .89) * 9))
    flecks = [(-.32, .43, .24, .23, 1), (.40, -.31, .12, .15, .96), (-.32, -.53, .10, .10, .62)]
    for cx, cy, rx, ry, strength in flecks:
        shape = 1 - sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
        blue = mix_color(blue, (.94, .99, 1, 1), strength * max(0, min(1, shape * 10)))
    return blue


def apron_paint(u, v):
    x, y = .48 - u, v - .44
    pale = (.94, .95, .99, 1)
    whale_blue = (.26, .55, .87, 1)
    body = 1 - sqrt(((x + .02) / .145) ** 2 + ((y + .033) / .12) ** 2)
    tail = max(
        1 - sqrt(((x - .112) / .060) ** 2 + ((y - .006) / .032) ** 2),
        1 - sqrt(((x - .151 + y * .29) / .036) ** 2 + ((y - .055) / .050) ** 2),
        1 - sqrt(((x - .095 + y * .18) / .030) ** 2 + ((y - .077) / .041) ** 2),
    )
    splash = max(1 - sqrt(((x + cx + y * shift) / .014) ** 2 + ((y - cy) / .022) ** 2)
                 for cx, cy, shift in [(0.04, .156, .22), (.075, .125, -.32), (.013, .137, .14)])
    paint = mix_color(pale, whale_blue, max(0, min(1, max(body, tail, splash) * 17)))
    eye = sqrt((x + .098) ** 2 + (y - .012) ** 2)
    if eye < .012:
        paint = (.05, .17, .38, 1)
    smile = -.083 + 3.5 * (x + .055) ** 2
    if -.12 < x < .010 and abs(y - smile) < .005:
        paint = (.90, .99, 1, 1)
    return paint


paint = material("Hand-painted satin", "FFFFFF", .37, vertex=True)
skin = material("Peach porcelain", "F8CFC4", .48)
skin_tip = material("Rose blush", "F4B0A9", .49)
navy = material("Sapphire uniform", "29478F", .45)
blue = material("Blue ribbons", "3459A7", .38)
shoe = material("Glazed sapphire shoes", "274EA3", .25)
sole = material("Rubber sole", "203B78", .56)
white = material("Pearl cotton", "F5F3FF", .58)
shadow_white = material("Lavender lining", "DBDFF3", .56)
eyeliner = material("Deep indigo lashes", "192745", .58)
mouth = material("Soft cherry mouth", "8C3844", .54)
tongue = material("Petal tongue", "E47F80", .54)
iris = material("Painted sapphire irises", "FFFFFF", .35, texture=painted_image("Iris paint", 128, iris_paint))
apron = material("Painted whale apron", "FFFFFF", .57, texture=painted_image("Whale emblem", 256, apron_paint))
hair_colors = [rgba(h) for h in ("3765B0", "4E82D0", "6AA3EA", "71ADF0", "5091DC")]
fin_colors = [rgba(h) for h in ("5393DC", "65AAE9", "91CDF6", "AADCF9")]

# All surfaces are combined into a single indexed skinned mesh. The shape builders
# attach each vertex to the nearest joint or interpolate a pair of adjacent joints.
vertices, polygons, face_materials, colors, uv_coords, skinning = [], [], [], [], [], []
materials = [paint, skin, skin_tip, navy, blue, shoe, sole, white, shadow_white, eyeliner, mouth, tongue, iris, apron]


def add_surface(points, faces, mat, weights, tint=None, uv=None):
    start = len(vertices)
    vertices.extend(points)
    polygons.extend(tuple(start + i for i in f) for f in faces)
    face_materials.extend([materials.index(mat)] * len(faces))
    colors.extend(tint if tint is not None else [(1, 1, 1, 1)] * len(points))
    uv_coords.extend(uv if uv is not None else [(0, 0)] * len(points))
    skinning.extend([{weights: 1}] * len(points) if isinstance(weights, str) else weights)


def rings_faces(count, radial):
    return [(j * radial + k, j * radial + (k + 1) % radial,
             (j + 1) * radial + (k + 1) % radial, (j + 1) * radial + k)
            for j in range(count - 1) for k in range(radial)]


def ellipsoid(center, radii, mat, weight, rotate=(0, 0, 0), radial=22, levels=12, tint=None):
    radial = max(9, round(radial * .68))
    levels = max(5, round(levels * .61))
    rotation = Euler(rotate).to_matrix()
    points, tints = [], []
    for j in range(1, levels):
        polar = pi * j / levels
        for k in range(radial):
            angle = TAU * k / radial
            point = (radii[0] * sin(polar) * cos(angle), radii[1] * sin(polar) * sin(angle),
                     radii[2] * cos(polar))
            points.append(Vector(center) + rotation @ Vector(point))
            if tint:
                tints.append(tint(polar, angle))
    faces = [tuple(reversed(f)) for f in rings_faces(levels - 1, radial)]
    for sign in (1, -1):
        pole = len(points)
        points.append(Vector(center) + rotation @ Vector((0, 0, sign * radii[2])))
        if tint:
            tints.append(tint(0 if sign > 0 else pi, 0))
        for k in range(radial):
            j = (k + 1) % radial
            tail = (levels - 2) * radial
            faces.append((pole, k, j) if sign > 0 else (pole, tail + j, tail + k))
    add_surface(points, faces, mat, weight, tints if tint else None)


def interpolate(samples, index, fraction):
    a, b = samples[index], samples[index + 1]
    previous, following = samples[max(0, index - 1)], samples[min(len(samples) - 1, index + 2)]
    f2, f3 = fraction * fraction, fraction ** 3
    return a * (2 * f3 - 3 * f2 + 1) + b * (-2 * f3 + 3 * f2) + (
        (b - previous) * (f3 - 2 * f2 + fraction) + (following - a) * (f3 - f2)
    ) * .5


def tube(sections, mat, weights, *, axis=(1, 0, 0), radial=12, grain=0, palette=None, belly=None):
    """Sweep a closed elliptical section along a smooth, tapered centerline."""
    positions = [Vector(row[0]) for row in sections]
    widths = [Vector(row[1:3]) for row in sections]
    samples = [(index, segment / 2) for index in range(len(sections) - 1) for segment in range(2)]
    samples.append((len(sections) - 2, 1))
    centers = [interpolate(positions, i, t) for i, t in samples]
    points, tints, groups = [], [], []
    previous_tangent = None
    side = Vector(axis)
    for j, (index, fraction) in enumerate(samples):
        center = centers[j]
        radius = interpolate(widths, index, fraction)
        tangent = (centers[min(j + 1, len(centers) - 1)] - centers[max(0, j - 1)]).normalized()
        if previous_tangent is None:
            side -= tangent * tangent.dot(side)
            side.normalize()
        else:
            side = previous_tangent.rotation_difference(tangent) @ side
        previous_tangent = tangent
        depth = tangent.cross(side).normalized()
        t = j / (len(samples) - 1)
        for k in range(radial):
            a = TAU * k / radial
            rib = 1 + grain * cos(5 * a + 2 * t)
            radial_direction = side * cos(a) + depth * sin(a)
            points.append(center + side * max(.0005, radius.x) * cos(a) * rib +
                          depth * max(.0005, radius.y) * sin(a) * rib)
            if palette:
                base = mix_color(palette[index], palette[index + 1], fraction)
                shade = .90 + .10 * cos(a + .4) ** 2 + grain * cos(5 * a + 2 * t)
                if belly:
                    edge = min(1, max(0, (-radial_direction.z - .43) * 5))
                    fade = sin(pi * t) ** .26
                    base = mix_color(base, belly, edge * fade)
                tints.append(tuple(v * shade for v in base[:3]) + (1,))
            if not isinstance(weights, str):
                groups.append(weights(t))
    faces = [tuple(reversed(range(radial)))] + rings_faces(len(samples), radial)
    faces.append(tuple(range(len(points) - radial, len(points))))
    add_surface(points, faces, mat, groups if groups else weights, tints if palette else None)


def layer(rings, bone, palette, pleats=10, wave=.08, radial=72):
    points, tints = [], []
    for j, (z, wide, depth, ruffle) in enumerate(rings):
        for k in range(radial):
            angle = TAU * k / radial
            fold = cos(pleats * angle + .15 * sin(angle))
            offset = wave * (j + 1) / len(rings) * fold
            points.append((wide * (1 + offset) * cos(angle), depth * (1 + offset) * sin(angle),
                           z + ruffle * cos(pleats * angle)))
            tints.append(mix_color(palette[j], palette[-1], max(0, -fold * .23)))
    faces = [tuple(reversed(f)) for f in rings_faces(len(rings), radial)]
    add_surface(points, faces, paint, bone, tints)


def panel(cx, cy, cz, rx, rz, depth, mat, weight, *, turn=0, tilt=0, radial=28):
    """Raised cloth or face patch with disk UVs, on the +Y side of the character."""
    points, uvs = [], []
    rings = 4
    for step in range(1, rings + 1):
        r = step / rings
        for k in range(radial):
            a = TAU * k / radial
            x, z = r * cos(a), r * sin(a)
            points.append((cx + rx * x, cy + depth * (1 - r * r) + turn * x + tilt * z, cz + rz * z))
            uvs.append((.5 + .5 * x, .5 + .5 * z))
    points.append((cx, cy + depth, cz))
    uvs.append((.5, .5))
    faces = rings_faces(rings, radial) + [(len(points) - 1, (k + 1) % radial, k) for k in range(radial)]
    add_surface(points, faces, mat, weight, uv=uvs)


def stripe(points, radii, mat, bone, *, axis=(1, 0, 0), palette=None, grain=0, belly=None):
    tube([(point, w, d) for point, (w, d) in zip(points, radii)], mat, bone,
         axis=axis, palette=palette, grain=grain, belly=belly)


def blend_bones(a, b, t, start=.28, end=.74):
    t = min(1, max(0, (t - start) / (end - start)))
    s = t * t * (3 - 2 * t)
    return {a: 1 - s, b: s}


def tail_weights(t):
    # The two bend joints coil the tail around the hips during the roll.
    first = blend_bones("Tail", "TailCurl", t, .06, .28)["TailCurl"]
    second = blend_bones("TailCurl", "TailCurlTip", t, .24, .48)["TailCurlTip"]
    last = blend_bones("TailCurlTip", "Flukes", t, .57, .98)["Flukes"]
    return {"Tail": (1 - first) * (1 - last), "TailCurl": first * (1 - second) * (1 - last),
            "TailCurlTip": first * second * (1 - last), "Flukes": last}


# Head. Layered hair locks form one continuous rear silhouette with individual
# curls under it. The scalloped headband runs across the crown, not around the face.
head = "Head"
ellipsoid((0, .044, 1.265), (.198, .162, .212), skin, head, radial=48, levels=28)
ellipsoid((0, -.056, 1.359), (.236, .208, .208), paint, head, radial=48, levels=26,
          tint=lambda p, a: mix_color(hair_colors[2], hair_colors[0], p / pi))
# The inner hair follows the head, covering the nape as the outer curls swing.
ellipsoid((0, -.082, 1.234), (.186, .147, .164), paint, head, radial=36, levels=20,
          tint=lambda p, a: mix_color(hair_colors[1], hair_colors[0], p / pi))
for side in (-1, 1):
    x = side * .092
    panel(x, .167, 1.296, .071, .071, .031, eyeliner, head, turn=-side * .017, tilt=.002)
    panel(x, .170, 1.289, .063, .062, .032, white, head, turn=-side * .016)
    panel(x - side * .003, .185, 1.291, .049, .056, .023, iris, head, turn=-side * .012)
    ellipsoid((side * .125, .176, 1.215), (.039, .018, .017), skin_tip, head, (0, 0, -side * .55))
    stripe([(side * .053, .195, 1.377), (side * .080, .187, 1.389),
            (side * .108, .172, 1.388), (side * .131, .153, 1.378)],
           [(.002, .002), (.007, .003), (.006, .003), (.002, .002)], eyeliner, head, axis=(0, 0, 1))
ellipsoid((0, .189, 1.239), (.020, .023, .018), skin, head)
panel(0, .196, 1.193, .042, .027, .009, mouth, head)
panel(0, .201, 1.186, .030, .012, .009, tongue, head)
panel(0, .201, 1.205, .030, .006, .009, white, head)

for i in range(7):
    s = (i - 3) / 3
    points = [(s * .061 - .018, .045, 1.535 - abs(s) * .025),
              (s * .110 - .015, .127, 1.493 - abs(s) * .018),
              (s * .164 - .006, .162, 1.439 - abs(s) * .026),
              (s * .170 + .010, .181 - abs(s) * .027, 1.390 - abs(s) * .053),
              (s * .171 + .036, .183 - abs(s) * .067, 1.356 - abs(s) * .115)]
    stripe(points, [(.030, .016), (.044, .027), (.046, .035), (.036, .025), (.001, .001)],
           paint, head, palette=[hair_colors[j] for j in (1, 2, 3, 2, 0)], grain=.045)

for i in range(7):
    s = (i - 3) / 3
    outside = abs(s)
    curl = .036 + .016 * cos(i * 2.1)
    tip_z = .907 + .028 * cos(i * 2.2) + .025 * outside
    points = [(s * .052, -.161, 1.484 - outside * .034),
              (s * .115, -.218 + outside * .024, 1.434 - outside * .024),
              (s * .182, -.241 + outside * .046, 1.330),
              (s * .203, -.217 + outside * .035, 1.205),
              (s * .211 - .024, -.234 + outside * .021, 1.062),
              (s * .217 - .041, -.286 - outside * .010, .980 + .023 * outside),
              (s * .223 - .025, -.329, tip_z),
              (s * .227 + .019, -.338, tip_z - .004),
              (s * .229 + .049, -.317, tip_z + curl),
              (s * .231 + .044, -.296, tip_z + curl + .023)]
    stripe(points, [(.021, .015), (.047, .029), (.061, .039), (.069, .041), (.068, .048),
                    (.059, .045), (.045, .033), (.036, .023), (.019, .012), (.003, .003)],
           paint, lambda t: blend_bones(head, "Hair", t, .39, .88),
           palette=[hair_colors[j] for j in (2, 2, 2, 1, 2, 3, 2, 2, 1, 0)], grain=.028)

for s in (-1, 1):
    stripe([(s * .186, -.095, 1.336), (s * .204, -.091, 1.180),
            (s * .235, -.122, 1.101), (s * .306, -.186, 1.042),
            (s * .335, -.239, .991), (s * .310, -.276, .953),
            (s * .274, -.269, .954), (s * .261, -.255, .976)],
           [(.036, .021), (.048, .031), (.047, .031), (.035, .025), (.029, .023),
            (.022, .016), (.014, .012), (.002, .002)],
           paint, lambda t: blend_bones(head, "Hair", t, .40, .82),
           palette=[hair_colors[j] for j in (0, 1, 2, 3, 2, 1, 0, 0)], grain=.022)

for side in (-1, 1):
    stripe([(side * .182, .038, 1.315), (side * .236, .028, 1.303),
            (side * .268, .006, 1.267), (side * .321, -.016, 1.250),
            (side * .361, -.018, 1.267)],
           [(.041, .032), (.054, .043), (.048, .032), (.030, .019), (.001, .001)],
           paint, head, axis=(0, 0, 1), palette=[fin_colors[j] for j in (0, 1, 2, 3, 2)], grain=.07)
    for branch in range(3):
        stripe([(side * .226, .047, 1.310 - branch * .019),
                (side * (.268 + .016 * branch), .036 - .008 * branch, 1.282 - branch * .012),
                (side * (.279 + .024 * branch), .021 - .005 * branch, 1.236 + branch * .008)],
               [(.010, .005), (.016, .007), (.001, .002)], paint, head, axis=(0, 0, 1),
               palette=[fin_colors[j] for j in (1, 3, 2)])
    ellipsoid((side * .232, -.100, 1.364), (.043, .037, .059), blue, head, (0, side * .23, 0))
    ellipsoid((side * .254, -.144, 1.391), (.060, .030, .047), blue, head, (0, side * .46, 0))
    ellipsoid((side * .254, -.156, 1.335), (.053, .025, .039), navy, head, (0, -side * .43, 0))
    stripe([(side * .236, -.135, 1.349), (side * .241, -.168, 1.281), (side * .256, -.180, 1.218)],
           [(.022, .013), (.026, .012), (.017, .004)], blue, head)

for i in range(17):
    a = -1.20 + 2.40 * i / 16
    ellipsoid((.224 * sin(a), -.026 - .017 * cos(a), 1.350 + .207 * cos(a)),
              (.035, .040, .030 + .006 * cos(a)), white, head, (0, a, 0), radial=16, levels=10)
stripe([(-.021, -.054, 1.534), (-.080, -.048, 1.575), (-.103, -.047, 1.630),
        (-.088, -.040, 1.676), (-.039, -.032, 1.701), (.009, -.029, 1.684), (.026, -.027, 1.652)],
       [(.016, .017), (.022, .019), (.023, .018), (.019, .017), (.016, .014),
        (.013, .012), (.002, .003)], paint,
       lambda t: blend_bones(head, "Ahoge", t, .05, .60),
       palette=[hair_colors[j] for j in (0, 1, 2, 3, 3, 2, 1)])

# Dress. Broad waist bow and ruffled skirt have their own layers and silhouette.
torso = "Chest"
ellipsoid((0, .013, 1.031), (.075, .072, .066), skin, torso)
ellipsoid((0, .007, .888), (.151, .111, .156), navy, torso)
ellipsoid((0, .012, .765), (.135, .110, .045), white, torso)
ellipsoid((0, .063, .950), (.110, .073, .060), white, torso)
ellipsoid((0, .094, .881), (.067, .034, .070), shadow_white, torso)
for side in (-1, 1):
    for i in range(7):
        t = i / 6
        ellipsoid((side * (.108 - .035 * t), .083 + .029 * sin(pi * t), .956 - .147 * t),
                  (.023, .022, .018), white, torso, (0, side * .29, 0), radial=14, levels=8)
    ellipsoid((side * .042, .133, .933), (.053, .021, .028), blue, torso, (0, side * -.34, 0))
    ellipsoid((side * .083, -.118, .769), (.102, .041, .053), white, torso, (0, side * -.36, 0))
    stripe([(side * .040, -.145, .749), (side * .077, -.161, .709),
            (side * .120, -.170, .653), (side * .132, -.180, .624)],
           [(.028, .021), (.043, .019), (.050, .014), (.040, .009)], white, torso)
ellipsoid((0, .151, .931), (.023, .018, .025), navy, torso)
ellipsoid((0, -.154, .761), (.038, .029, .036), white, torso)
for z in (.902, .876, .852):
    ellipsoid((0, .131, z), (.009, .007, .009), blue, torso, radial=12, levels=8)

layer([(.750, .126, .102, .000), (.691, .175, .140, .004), (.621, .233, .184, .009),
       (.549, .301, .229, .017), (.523, .311, .232, .015), (.507, .285, .211, .014)],
      "Skirt", [rgba(h) for h in ("263F88", "3050A0", "3656A4", "3B5DAE", "304F96", "253D81")], wave=.076)
layer([(.549, .277, .199, .009), (.514, .313, .233, .013), (.480, .326, .250, .012),
       (.459, .311, .232, .010), (.458, .278, .211, .009)],
      "Skirt", [rgba(h) for h in ("DCE1F4", "EFEDFF", "FDFBFF", "E9E8FB", "CFD8EF")], pleats=17, wave=.086)
layer([(.567, .283, .213, .010), (.536, .313, .234, .013), (.519, .302, .220, .012)],
      "Skirt", [rgba(h) for h in ("3455A1", "3B60AD", "294687")], wave=.082)

panel(0, .185, .645, .175, .112, .033, apron, "Skirt", tilt=-.050)
for i in range(17):
    a = .17 + (pi - .34) * i / 16
    ellipsoid((.174 * cos(a), .182 + .048 * sin(a), .645 - .109 * sin(a)),
              (.025, .023, .024), white, "Skirt", (.30, -.28 * cos(a), 0), radial=14, levels=9)

# Tail, with a lighter underside and two sculpted flukes. The tip bends with its own bone.
tail_centers = [(0, -.095, .687), (0, -.198, .602), (0, -.297, .510),
                (0, -.383, .477), (0, -.464, .482), (0, -.552, .535), (0, -.595, .579)]
stripe(tail_centers, [(.071, .060), (.088, .073), (.100, .077), (.103, .076),
                     (.086, .064), (.063, .049), (.029, .029)], paint,
       tail_weights,
       palette=[hair_colors[j] for j in (0, 1, 2, 2, 3, 3, 2)], belly=rgba("C8DAF8"))
half_flukes = [((.211, -.715, .647), .002, .002), ((.187, -.689, .614), .044, .019),
               ((.132, -.651, .577), .071, .036), ((.065, -.612, .559), .078, .042)]
fluke_shape = [((-x, y, z), wide, depth) for (x, y, z), wide, depth in half_flukes]
fluke_shape.append(((0, -.583, .550), .066, .036))
fluke_shape.extend(reversed(half_flukes))
tube(fluke_shape, paint, "Flukes", axis=(0, 1, 0), radial=16,
     palette=[hair_colors[j] for j in (1, 2, 3, 2, 2, 2, 3, 2, 1)], belly=rgba("9CC5F3"))

# Fitted humanoid bone map. Define the joints alongside the shape sizes.
bones = {}
def bone(name, start, end, parent=None):
    bones[name] = (start, end, parent)

bone("Root", (0, 0, 0), (0, 0, .11))
bone("Pelvis", (0, 0, .545), (0, 0, .689), "Root")
bone("Chest", (0, 0, .689), (0, .019, 1.022), "Pelvis")
bone("Head", (0, .019, 1.022), (0, .026, 1.392), "Chest")
bone("Hair", (0, -.191, 1.249), (0, -.270, .936), "Head")
bone("Ahoge", (-.034, -.052, 1.544), (-.076, -.039, 1.650), "Head")
bone("Skirt", (0, 0, .744), (0, 0, .483), "Pelvis")
bone("Tail", (0, -.095, .687), (0, -.198, .602), "Pelvis")
bone("TailCurl", (0, -.198, .602), (0, -.297, .510), "Tail")
bone("TailCurlTip", (0, -.297, .510), (0, -.465, .480), "TailCurl")
bone("Flukes", (0, -.465, .480), (0, -.621, .578), "TailCurlTip")
for side, suffix in [(-1, "L"), (1, "R")]:
    upper_arm, lower_arm, hand = ["%s.%s" % (s, suffix) for s in ("Arm", "Forearm", "Hand")]
    upper_leg, lower_leg, foot = ["%s.%s" % (s, suffix) for s in ("Thigh", "Shin", "Foot")]
    shoulder, elbow, wrist = (side * .136, 0, .940), (side * .259, .007, .818), (side * .354, .022, .743)
    hip, knee, ankle = (side * .107, 0, .565), (side * .113, .010, .332), (side * .119, -.005, .103)
    bone(upper_arm, shoulder, elbow, "Chest")
    bone(lower_arm, elbow, wrist, upper_arm)
    bone(hand, wrist, (side * .404, .029, .705), lower_arm)
    bone(upper_leg, hip, knee, "Pelvis")
    bone(lower_leg, knee, ankle, upper_leg)
    bone(foot, ankle, (side * .119, .082, .034), lower_leg)

    stripe([shoulder, (side * .196, 0, .878), elbow, (side * .312, .014, .774), wrist],
           [(.044, .045), (.053, .052), (.045, .041), (.038, .038), (.027, .027)], skin,
           lambda t: blend_bones(upper_arm, lower_arm, t, .30, .74), axis=(0, 1, 0))
    ellipsoid((side * .175, -.002, .911), (.076, .075, .084), navy, upper_arm, (0, -side * .49, 0))
    ellipsoid((side * .224, .004, .856), (.062, .062, .031), white, upper_arm, (0, -side * .62, 0))
    for i in range(9):
        a = TAU * i / 9
        ellipsoid((side * (.230 + .029 * cos(a)), .003 + .047 * sin(a), .852 + .027 * cos(a)),
                  (.017, .018, .014), shadow_white if i % 3 == 0 else white, upper_arm, radial=12, levels=8)
    ellipsoid((side * .376, .023, .728), (.043, .025, .035), skin, hand, (0, side * .59, 0))
    for i in range(4):
        x, z = side * (.383 + .007 * i), .709 + i * .012
        stripe([(x, .024, z), (x + side * (.022 - .002 * i), .027, z - .013 + .003 * i),
                (x + side * (.044 - .002 * i), .026, z - .020 + .004 * i)],
               [(.011, .012), (.010, .010), (.003, .004)], skin, hand, axis=(0, 1, 0))
    ellipsoid((side * .369, .046, .741), (.022, .016, .012), skin, hand, (0, side * -.40, 0))

    stripe([hip, (side * .110, -.002, .456), knee, (side * .115, -.003, .245),
            (side * .117, -.005, .161), ankle],
           [(.071, .067), (.069, .063), (.052, .053), (.057, .057), (.041, .044), (.043, .044)], skin,
           lambda t: blend_bones(upper_leg, lower_leg, t, .24, .56))
    ellipsoid((side * .119, -.003, .119), (.056, .052, .070), white, lower_leg)
    for level in range(2):
        for i in range(9):
            a = TAU * i / 9
            ellipsoid((side * .119 + .049 * cos(a), -.004 + .046 * sin(a), .155 + level * .023),
                      (.018, .015, .014), white, lower_leg, (0, 0, a), radial=12, levels=7)
    ellipsoid((side * .119, .037, .022), (.066, .095, .017), sole, foot)
    ellipsoid((side * .119, .038, .046), (.065, .094, .038), shoe, foot)
    ellipsoid((side * .119, .013, .078), (.052, .061, .024), white, foot)
    ellipsoid((side * .119, .029, .087), (.058, .024, .012), shoe, foot, (.21, 0, 0))
    for j in (-1, 1):
        ellipsoid((side * .174, .024 + j * .021, .079), (.021, .028, .025), shoe, foot, (.36 * j, 0, 0))
    ellipsoid((side * .186, .024, .079), (.017, .012, .015), blue, foot)


rig_data = bpy.data.armatures.new("Whale maid joints")
rig = bpy.data.objects.new("WhaleMaid", rig_data)
scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
rig.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
for name, (start, end, parent) in bones.items():
    joint = rig_data.edit_bones.new(name)
    joint.head, joint.tail = start, end
    if parent:
        joint.parent = rig_data.edit_bones[parent]
bpy.ops.object.mode_set(mode="OBJECT")

data = bpy.data.meshes.new("Sculpted whale maid")
data.from_pydata(vertices, [], polygons)
data.update()
for mat in materials:
    data.materials.append(mat)
for polygon, material_index in zip(data.polygons, face_materials):
    polygon.material_index = material_index
    polygon.use_smooth = True
data.color_attributes.new(name="Paint", type="BYTE_COLOR", domain="POINT").data.foreach_set(
    "color", [channel for color in colors for channel in color]
)
uv = data.uv_layers.new(name="UVMap")
uv.uv.foreach_set("vector", [coordinate for loop in data.loops for coordinate in uv_coords[loop.vertex_index]])
model = bpy.data.objects.new("Whale maid surface", data)
scene.collection.objects.link(model)
model.parent = rig
groups = {name: model.vertex_groups.new(name=name) for name in bones}
for index, weights in enumerate(skinning):
    for name, value in weights.items():
        if value > 0:
            groups[name].add([index], value, "REPLACE")
modifier = model.modifiers.new("Deform from fitted joints", "ARMATURE")
modifier.object = rig

poses = rig.pose.bones
axes = {name: bone.matrix_local.to_quaternion() for name, bone in rig_data.bones.items()}
floor_points = [(Vector(p), next(iter(w))) for p, w in zip(vertices, skinning)
                if any(name.startswith("Foot.") for name in w)]


def set_rotation(name, x=0, y=0, z=0):
    axis = axes[name]
    poses[name].rotation_quaternion = axis.inverted() @ Euler((x, y, z)).to_quaternion() @ axis


def floor_pose(offset=0):
    # The game owns jump height and running distance. For grounded frames, make
    # the shoe that supports the pose meet the floor without adding root motion.
    bpy.context.view_layer.update()
    transforms = {name: poses[name].matrix @ rig_data.bones[name].matrix_local.inverted()
                  for name in ("Foot.L", "Foot.R")}
    lowest = min((transforms[name] @ p).z for p, name in floor_points)
    poses["Root"].location = axes["Root"].inverted() @ Vector((0, 0, offset - lowest))


def running(t):
    phase = TAU * t
    set_rotation("Pelvis", z=.065 * sin(phase))
    set_rotation("Chest", x=-.15, z=-.12 * sin(phase))
    set_rotation("Head", x=.073, z=.035 * sin(phase))
    set_rotation("Hair", x=.062 * cos(phase * 2 - .6), z=.091 * sin(phase - .52))
    set_rotation("Skirt", x=-.054 + .04 * cos(phase * 2), y=.053 * sin(phase))
    set_rotation("Tail", x=.12 * cos(phase * 2 - .66), z=.17 * sin(phase - .76))
    set_rotation("Flukes", x=.20 * cos(phase * 2 - 1.2), z=.11 * sin(phase - 1.2))
    for i, suffix in enumerate(("L", "R")):
        side = 2 * i - 1
        stride = sin(phase + i * pi)
        lift = max(0, cos(phase + i * pi))
        set_rotation("Thigh." + suffix, x=.61 * stride + .04)
        set_rotation("Shin." + suffix, x=-.12 - .95 * lift)
        set_rotation("Foot." + suffix, x=.28 * lift - .16 * stride)
        set_rotation("Arm." + suffix, x=-.66 * stride, y=side * .50)
        set_rotation("Forearm." + suffix, x=.95 + .16 * stride)
        set_rotation("Hand." + suffix, y=-side * .08)
    floor_pose(.004 + .018 * cos(phase * 2) ** 4)


def jumping(t):
    tuck = sin(pi * t) ** 1.15
    set_rotation("Chest", x=-.27 * tuck)
    set_rotation("Head", x=.19 * tuck)
    set_rotation("Hair", x=-.20 * tuck)
    set_rotation("Skirt", x=-.11 * tuck)
    set_rotation("Tail", x=-.29 * tuck)
    set_rotation("Flukes", x=-.22 * tuck)
    for i, suffix in enumerate(("L", "R")):
        side = 2 * i - 1
        set_rotation("Thigh." + suffix, x=(.95 - .47 * i) * tuck)
        set_rotation("Shin." + suffix, x=-(1.20 - .36 * i) * tuck)
        set_rotation("Foot." + suffix, x=.21 * tuck)
        set_rotation("Arm." + suffix, x=(.82 - .26 * i) * tuck, y=side * (.34 - .18 * tuck))
        set_rotation("Forearm." + suffix, x=.48 * tuck)


def ease(value):
    value = max(0, min(1, value))
    return value * value * (3 - 2 * value)


def rolling(t):
    tuck = ease(t / .18) * ease((1 - t) / .18)
    turn = ease((t - .08) / .82)
    # The pelvis rotates around the tucked body. The game's track position stays
    # fixed while the root rises or falls as shoulders, back and feet take contact.
    set_rotation("Pelvis", x=-TAU * turn)
    # This root's local Y points up. Squash only during the tucked shape so
    # large hair and tail forms keep their width and fit beneath the crossbar.
    poses["Root"].scale.y = 1 - .14 * tuck
    set_rotation("Chest", x=-1.98 * tuck)
    set_rotation("Head", x=-.96 * tuck)
    set_rotation("Hair", x=.38 * tuck)
    set_rotation("Ahoge", x=-1.38 * tuck)
    set_rotation("Skirt", x=.36 * tuck)
    set_rotation("Tail", x=-2.72 * tuck)
    set_rotation("TailCurl", x=-1.16 * tuck)
    set_rotation("TailCurlTip", x=-.92 * tuck)
    set_rotation("Flukes", x=-.86 * tuck)
    for side, suffix in [(-1, "L"), (1, "R")]:
        set_rotation("Thigh." + suffix, x=1.94 * tuck, y=.18 * side * tuck)
        set_rotation("Shin." + suffix, x=-2.13 * tuck)
        set_rotation("Foot." + suffix, x=.44 * tuck)
        set_rotation("Arm." + suffix, x=.70 * tuck, y=.56 * side * tuck)
        set_rotation("Forearm." + suffix, x=1.52 * tuck)
        set_rotation("Hand." + suffix, x=-.19 * tuck)

    bpy.context.view_layer.update()
    posed = model.evaluated_get(bpy.context.evaluated_depsgraph_get())
    surface = posed.to_mesh()
    ground = min(vertex.co.z for vertex in surface.vertices)
    posed.to_mesh_clear()
    poses["Root"].location = axes["Root"].inverted() @ Vector((0, 0, .006 + .008 * tuck - ground))


def reset_pose():
    for joint in poses:
        joint.rotation_mode = "QUATERNION"
        joint.rotation_quaternion = Quaternion()
        joint.location = (0, 0, 0)
        joint.scale = (1, 1, 1)


def animate(name, movement, intervals=24):
    for frame in range(intervals + 1):
        reset_pose()
        movement(frame / intervals)
        for joint in poses:
            joint.keyframe_insert(data_path="rotation_quaternion", frame=frame + 1, group=joint.name)
        for field in ("location", "scale"):
            poses["Root"].keyframe_insert(data_path=field, frame=frame + 1, group="Root")
    active = rig.animation_data.action
    active.name = name
    track = rig.animation_data.nla_tracks.new()
    track.name = name
    track.strips.new(name, 1, active)
    rig.animation_data.action = None
    track.mute = True


for name, move in [("Run", running), ("Jump", jumping), ("Roll", rolling)]:
    animate(name, move)
reset_pose()
for track in rig.animation_data.nla_tracks:
    track.mute = False
scene.frame_set(1)
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.export_scene.gltf(
    filepath=str(OUTPUT),
    export_format="GLB",
    export_yup=True,
    export_animations=True,
    export_animation_mode="NLA_TRACKS",
    export_merge_animation="NLA_TRACK",
    export_optimize_animation_size=True,
    export_rest_position_armature=True,
)
data.calc_loop_triangles()
print(f"Wrote {OUTPUT} with {len(data.loop_triangles):,} triangles, {len(bones)} joints and {len(materials)} materials")


def render_previews():
    for track in rig.animation_data.nla_tracks:
        track.mute = True
    world = bpy.data.worlds.new("Blue-grey studio")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (.15, .22, .34, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = .45
    scene.world = world
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 570
    scene.render.resolution_y = 690
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Khronos PBR Neutral"

    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.001))
    bpy.context.object.data.materials.append(material("Studio floor", "D8E4F7", .87))
    target = Vector((0, -.12, .84))
    for position, power, size, tint in [((2.7, -2.2, 4.2), 360, 4.1, (.79, .89, 1)),
                                       ((-2.6, 2.1, 3.4), 380, 3.4, (1, .90, .82)),
                                       ((.1, -3.6, 1.8), 102, 2.7, (.92, .96, 1))]:
        light = bpy.data.lights.new("Softbox", "AREA")
        light.energy, light.size, light.color = power, size, tint
        lamp = bpy.data.objects.new("Softbox", light)
        scene.collection.objects.link(lamp)
        lamp.location = position
        lamp.rotation_euler = (target - lamp.location).to_track_quat("-Z", "Y").to_euler()
    lens = bpy.data.cameras.new("Ortho")
    lens.type, lens.ortho_scale = "ORTHO", 1.99
    camera = bpy.data.objects.new("Reference camera", lens)
    scene.collection.objects.link(camera)
    scene.camera = camera

    for name, position, movement, t in [
        ("front", (.1, 3.6, 1.12), None, 0),
        ("side", (3.6, -.12, 1.10), None, 0),
        ("back", (0, -3.7, 1.19), None, 0),
        ("run", (-.48, -3.7, 1.54), running, .23),
        ("jump", (.70, -3.7, 1.55), jumping, .48),
        ("roll-early", (2.7, -3.2, 1.26), rolling, .28),
        ("roll-mid", (2.7, -3.2, 1.26), rolling, .50),
        ("roll-late", (2.7, -3.2, 1.26), rolling, .73),
    ]:
        reset_pose()
        if movement:
            movement(t)
        camera.location = position
        camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(ROOT / "output" / f"whale-maid-{name}.png")
        bpy.ops.render.render(write_still=True)


if "--" in sys.argv and "--render" in sys.argv[sys.argv.index("--") + 1:]:
    render_previews()
