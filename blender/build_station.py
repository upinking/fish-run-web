"""Build the station's reusable Blender meshes and export five glTF binaries.

Run: Blender --background --python blender/build_station.py
Lengths and model vertices below use glTF axes (Y up, travel towards -Z).
"""
from collections import defaultdict
from math import cos, pi, sin, sqrt
from pathlib import Path

import bpy


MODELS = Path(__file__).resolve().parents[1] / "public" / "models"
LANES = (-2.35, 0, 2.35)
LENGTH = 40
PALETTE = {
    "Bed": ("667581", 0.0, .88),
    "Ballast": ("89949D", 0.0, .93),
    "Sleeper": ("A7ACAF", .05, .78),
    "RailWeb": ("5C6976", .35, .48),
    "RailFace": ("BACAD2", .4, .29),
    "Concrete": ("DDE3E1", .0, .81),
    "TileA": ("EBE9DC", .0, .66),
    "TileB": ("E2E7E1", .0, .70),
    "BlueStone": ("8AAEB6", .02, .58),
    "Aqua": ("74D5CC", .05, .45),
    "Tactile": ("E6B76C", .0, .69),
    "White": ("F3F2E7", .02, .39),
    "Navy": ("294D68", .03, .50),
    "LeafA": ("77A65C", .0, .78),
    "LeafB": ("ABC46E", .0, .76),
    "LeafC": ("53956B", .0, .74),
    "Teal": ("39AEA8", .05, .40),
    "TealInner": ("245F71", .06, .51),
    "GlassA": ("A3E2EA", .03, .28, .37),
    "GlassB": ("79C4DF", .03, .31, .43),
    "Trim": ("297CAC", .02, .41),
    "Silver": ("DEE9EC", .22, .35),
    "TrainBlue": ("377CB9", .12, .37),
    "TrainAqua": ("67C5DF", .10, .42),
    "Window": ("173752", .12, .23),
    "Reflect": ("3E7B9D", .05, .27),
    "Rubber": ("343D48", .0, .71),
    "Orange": ("F2783E", .01, .46),
    "OrangeDark": ("C3522B", .02, .56),
    "Cream": ("FFEDD0", .0, .43),
    "Amber": ("F7C552", .03, .40),
    "AmberDark": ("A56B22", .02, .55),
    "WarmLight": ("FFF1C9", .0, .29, 1.0, .55),
    "CyanLight": ("C5FFEF", .0, .29, 1.0, .5),
}


def linear(channel):
    value = int(channel, 16) / 255
    return value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4


def get_material(name):
    material = bpy.data.materials.get(name)
    if material:
        return material
    color, metal, roughness, *options = PALETTE[name]
    alpha = options[0] if options else 1.0
    emission = options[1] if len(options) > 1 else 0.0
    rgba = tuple(linear(color[i:i + 2]) for i in (0, 2, 4)) + (alpha,)
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.use_backface_culling = alpha == 1.0
    material.diffuse_color = rgba
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = rgba
    shader.inputs["Metallic"].default_value = metal
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Alpha"].default_value = alpha
    if alpha < 1:
        material.surface_render_method = "BLENDED"
    if emission > 0:
        shader.inputs["Emission Color"].default_value = rgba
        shader.inputs["Emission Strength"].default_value = emission
    return material


class Parts:
    """Batch static pieces by material to keep each glTF instance inexpensive."""

    def __init__(self):
        self.meshes = defaultdict(lambda: ([], [], []))

    def mesh(self, color, vertices, faces, smooth=False):
        positions, polygons, smoothing = self.meshes[color]
        base = len(positions)
        positions.extend((x, -z, y) for x, y, z in vertices)
        polygons.extend(tuple(base + i for i in face) for face in faces)
        smoothing.extend([smooth] * len(faces))

    def box(self, color, x, y, z, width, height, depth):
        a, b, c = width / 2, height / 2, depth / 2
        vertices = [(x + sx * a, y + sy * b, z + sz * c) for sx, sy, sz in (
            (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
            (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
        )]
        faces = [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4),
                 (2, 3, 7, 6), (0, 4, 7, 3), (1, 2, 6, 5)]
        self.mesh(color, vertices, faces)

    def faceplate(self, color, points, back, front):
        """Extrude an XY polygon. The front is towards +Z."""
        n = len(points)
        vertices = [(x, y, z) for z in (back, front) for x, y in points]
        faces = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
        faces.extend((i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n))
        self.mesh(color, vertices, faces)

    def rounded(self, color, x, y, z, w, h, depth, radius, n=4):
        points = []
        for quadrant, (dx, dy) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
            cx, cy = x + dx * (w / 2 - radius), y + dy * (h / 2 - radius)
            points.extend((cx + radius * cos((quadrant + step / n) * pi / 2),
                           cy + radius * sin((quadrant + step / n) * pi / 2))
                          for step in range(n + 1))
        self.faceplate(color, points, z - depth / 2, z + depth / 2)

    def ellipsoid(self, color, x, y, z, rx, ry, rz, n=12, bands=6):
        vertices = [(x, y - ry, z)]
        for k in range(1, bands):
            latitude = -pi / 2 + pi * k / bands
            for i in range(n):
                angle = 2 * pi * i / n
                vertices.append((x + rx * cos(latitude) * cos(angle),
                                 y + ry * sin(latitude),
                                 z + rz * cos(latitude) * sin(angle)))
        vertices.append((x, y + ry, z))
        faces = []
        top = len(vertices) - 1
        for i in range(n):
            j = (i + 1) % n
            faces.append((0, 1 + i, 1 + j))
            for band in range(bands - 2):
                lo = 1 + band * n
                faces.append((lo + i, lo + n + i, lo + n + j, lo + j))
            faces.append((top, top - n + j, top - n + i))
        self.mesh(color, vertices, faces, smooth=True)

    def write(self, name):
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
        for color, (positions, polygons, smoothing) in self.meshes.items():
            mesh = bpy.data.meshes.new(f"{name}_{color}")
            mesh.from_pydata(positions, [], polygons)
            mesh.update()
            for polygon, smooth in zip(mesh.polygons, smoothing):
                polygon.use_smooth = smooth
            mesh.materials.append(get_material(color))
            obj = bpy.data.objects.new(f"{name}_{color}", mesh)
            bpy.context.collection.objects.link(obj)
        bpy.ops.export_scene.gltf(filepath=str(MODELS / f"{name}.glb"), export_format="GLB",
                                  export_animations=False, export_yup=True)


def track():
    part = Parts()
    part.box("Bed", 0, -.25, -20, 8.12, .4, LENGTH)
    for lane in LANES:
        part.box("Ballast", lane, -.068, -20, 2.22, .135, LENGTH)
        part.box("Bed", lane, -.009, -20, 1.82, .018, LENGTH)
        for i in range(50):
            z = -.4 - i * .8
            part.box("Sleeper", lane, .016, z, 1.81, .044, .235)
            for offset in (-.68, .68):
                part.box("RailWeb", lane + offset, .040, z, .153, .022, .155)
        for offset in (-.68, .68):
            x = lane + offset
            part.box("RailWeb", x, .051, -20, .075, .057, LENGTH)
            part.box("RailFace", x, .084, -20, .107, .022, LENGTH)

    for sign in (-1, 1):
        # A single platform substrate and shallow joints avoid openings at tile edges.
        part.box("Concrete", sign * 5.99, -.075, -20, 3.9, .61, LENGTH)
        part.box("BlueStone", sign * 4.04, -.055, -20, .13, .48, LENGTH)
        part.box("Aqua", sign * 4.06, .132, -20, .135, .072, LENGTH)
        part.box("White", sign * 4.09, .229, -20, .24, .05, LENGTH)
        part.box("Tactile", sign * 4.38, .235, -20, .225, .022, LENGTH)
        for i in range(25):
            z = -.8 - i * 1.6
            for j in range(3):
                part.box("TileB" if (i + 2 * j) % 4 == 0 else "TileA",
                         sign * (5.04 + 1.025 * j), .234, z, 1.007, .028, 1.575)
        # A slim railing leaves the sea visible behind the platform.
        part.box("White", sign * 7.82, .25, -20, .25, .07, LENGTH)
        part.box("BlueStone", sign * 7.83, .90, -20, .08, .06, LENGTH)
        part.box("RailFace", sign * 7.83, .62, -20, .04, .03, LENGTH)
        for i in range(10):
            part.box("White", sign * 7.83, .565, -2 - i * 4, .095, .64, .095)

        for z in (-5 - 2 * (sign > 0), -25 - 2 * (sign > 0)):
            lamp = sign * 7.30
            part.box("BlueStone", lamp, .328, z, .29, .14, .29)
            part.box("White", lamp, 1.82, z, .091, 3.02, .091)
            part.box("White", lamp - sign * .23, 3.36, z, .55, .075, .12)
            part.box("WarmLight", lamp - sign * .46, 3.30, z, .34, .048, .17)
        for z in (-12 - 3 * (sign > 0), -32 - 3 * (sign > 0)):
            x = sign * 6.89
            part.box("BlueStone", x, .454, z, .79, .40, 1.25)
            part.box("White", x, .644, z, .86, .13, 1.33)
            part.box("Bed", x, .710, z, .69, .025, 1.10)
            for dx, dz, h, color in (
                (-.18, -.31, .24, "LeafC"), (.18, -.19, .26, "LeafB"),
                (-.15, .15, .30, "LeafA"), (.16, .32, .23, "LeafC"),
                (-.06, -.06, .38, "LeafB"),
            ):
                part.ellipsoid(color, x + dx, .72 + h / 2, z + dz, .21, h / 1.5, .26, 8, 4)
        for z in (-18, -38):
            x = sign * 6.32
            for dz in (-.60, .60):
                part.box("BlueStone", x, .409, z + dz, .35, .33, .11)
            part.box("Aqua", x, .61, z, .47, .10, 1.57)
            part.box("White", x + sign * .22, .83, z, .08, .34, 1.50)
    part.write("track")


def arch_outline(radius_x, spring_y, radius_y):
    return [(-radius_x, .18)] + [
        (radius_x * cos(pi * (1 - i / 20)), spring_y + radius_y * sin(pi * (1 - i / 20)))
        for i in range(21)
    ] + [(radius_x, .18)]


def arch_ring(part, color, outer, inner, back, front):
    n = len(outer)
    vertices = [(x, y, z) for z in (back, front) for x, y in outer + inner]
    faces = []
    for i in range(n - 1):
        j = i + 1
        # Outline samples run from left to right over the arch.
        faces.extend(((i, j, n + j, n + i), (2*n+i, 3*n+i, 3*n+j, 2*n+j),
                      (i, 2*n+i, 2*n+j, j), (n+i, n+j, 3*n+j, 3*n+i)))
    faces.extend(((0, n, 3*n, 2*n), (n-1, 3*n-1, 4*n-1, 2*n-1)))
    part.mesh(color, vertices, faces)


def portal():
    part = Parts()
    outer = arch_outline(4.92, 2.86, 2.43)
    inner = arch_outline(4.19, 2.59, 1.89)
    arch_ring(part, "TealInner", outer, inner, -1.08, .18)
    arch_ring(part, "White", outer, arch_outline(4.77, 2.80, 2.37), .17, .42)
    arch_ring(part, "Teal", arch_outline(4.77, 2.80, 2.37), inner, .16, .45)
    arch_ring(part, "CyanLight", arch_outline(4.34, 2.65, 1.98),
              arch_outline(4.28, 2.63, 1.95), .451, .468)
    for side in (-1, 1):
        x = side * 4.60
        part.box("BlueStone", x, .15, -.22, .84, .27, 1.84)
        part.box("Navy", x, .90, .459, .18, .57, .025)
        part.box("WarmLight", x, 1.00, .476, .065, .28, .018)
    for t in (15, 35, 59, 82, 98, 121, 145, 165):
        angle = pi * t / 180
        x, y = 4.55 * cos(angle), 2.77 + 2.21 * sin(angle)
        part.ellipsoid("White", x, y, .467, .068, .068, .035, 10, 4)

    # Curved roof glazing follows the arch, with alternating pane colors.
    for i in range(12):
        a, b = pi * (1 - i / 12), pi * (1 - (i + 1) / 12)
        for depth_index in range(3):
            back = -.98 - depth_index * 1.10
            front = back + 1.05
            x1, y1 = 5.04 * cos(a), 3.08 + 2.80 * sin(a)
            x2, y2 = 5.04 * cos(b), 3.08 + 2.80 * sin(b)
            part.mesh("GlassA" if (i + depth_index) % 3 else "GlassB",
                      [(x1, y1, back), (x2, y2, back), (x2, y2, front), (x1, y1, front)],
                      [(0, 1, 2, 3)])
        if 0 < i < 12:
            part.box("White", 5.04 * cos(a), 3.08 + 2.80 * sin(a), -1.57, .065, .065, 3.27)
    for z in (.09, -1.01, -2.11, -3.21):
        arch_ring(part, "White", arch_outline(5.10, 3.10, 2.85),
                  arch_outline(5.00, 3.05, 2.78), z - .03, z + .03)
    for side in (-1, 1):
        part.box("White", side * 5.03, 1.64, -3.20, .16, 3.20, .16)

    # Stylized whale badge, raised from the lit face.
    part.ellipsoid("White", 0, 5.44, .48, .58, .34, .095, 24, 8)
    part.ellipsoid("Trim", -.10, 5.43, .571, .30, .135, .021, 18, 6)
    part.ellipsoid("Trim", .218, 5.47, .573, .13, .056, .018, 12, 4)
    part.ellipsoid("Trim", .31, 5.53, .573, .095, .044, .018, 12, 4)
    part.ellipsoid("Trim", .305, 5.425, .573, .084, .043, .018, 12, 4)
    part.ellipsoid("White", -.237, 5.47, .592, .025, .025, .009, 8, 4)
    part.write("portal")


def train():
    part = Parts()
    part.rounded("Silver", 0, 1.55, -.05, 1.99, 2.78, 4.78, .28)
    part.rounded("TrainBlue", 0, 1.58, 2.34, 2.01, 2.76, .14, .30)
    part.rounded("Silver", 0, 1.52, 2.422, 1.90, 2.50, .12, .27)
    part.rounded("Window", 0, 2.06, 2.49, 1.63, 1.12, .055, .23)
    part.rounded("Reflect", -.39, 2.08, 2.522, .69, .86, .02, .145)
    part.rounded("Reflect", .39, 2.08, 2.522, .69, .86, .02, .145)
    part.rounded("Navy", 0, 2.475, 2.543, .55, .144, .025, .058)
    for x in (-.18, 0, .18):
        part.box("CyanLight", x, 2.477, 2.561, .098, .027, .009)
    part.rounded("TrainBlue", 0, 1.02, 2.49, 1.76, .39, .065, .115)
    part.rounded("TrainAqua", 0, 1.21, 2.530, 1.50, .067, .014, .030)
    for x in (-.63, .63):
        part.rounded("Navy", x, .96, 2.535, .36, .173, .034, .080)
        part.rounded("WarmLight", x, .96, 2.556, .263, .092, .02, .043)
    part.rounded("Rubber", 0, .34, 2.43, 1.87, .30, .22, .11)
    part.rounded("RailFace", 0, .323, 2.55, .66, .082, .04, .032)
    part.box("Rubber", 0, .19, 0, 1.57, .25, 4.47)
    part.rounded("TrainBlue", 0, 2.808, -.12, 1.65, .31, 4.45, .12)
    for side in (-1, 1):
        part.box("TrainBlue", side * 1.003, 1.15, -.05, .036, .40, 4.62)
        part.box("TrainAqua", side * 1.024, 1.35, -.05, .009, .074, 4.60)
        for z in (-1.74, -.55, .65, 1.79):
            part.box("Navy", side * 1.003, 2.044, z, .033, .67, .77)
            part.box("Reflect", side * 1.023, 2.05, z, .014, .53, .63)
            part.box("Window", side * 1.031, 2.044, z + .08, .008, .55, .042)
        for z in (-1.50, 1.49):
            part.box("Rubber", side * .62, .137, z, .32, .21, .77)
    part.write("train")


def jump():
    part = Parts()
    for side in (-1, 1):
        part.rounded("OrangeDark", side * .69, .112, 0, .44, .22, .57, .073)
        part.box("Navy", side * .69, .076, 0, .29, .069, .62)
    part.rounded("OrangeDark", 0, .37, -.018, 1.88, .59, .405, .112)
    part.rounded("Orange", 0, .405, .025, 1.85, .55, .40, .112)
    part.rounded("Cream", 0, .587, .228, 1.56, .066, .012, .031)
    part.rounded("OrangeDark", 0, .35, .235, 1.38, .223, .025, .064)
    # Three upward chevrons distinguish jumpable obstacles by shape as well as color.
    for x in (-.43, 0, .43):
        part.faceplate("Cream", [(x-.097, .319), (x, .372), (x+.097, .319),
                                 (x+.097, .361), (x, .415), (x-.097, .361)], .249, .260)
    part.write("jump")


def slide():
    part = Parts()
    for side in (-1, 1):
        x = side * .88
        part.rounded("AmberDark", x, .08, 0, .26, .16, .40, .07)
        part.rounded("Amber", x, .63, 0, .16, 1.22, .20, .07)
        part.rounded("Cream", x, .246, .108, .09, .112, .02, .025)
    part.rounded("AmberDark", 0, 1.098, -.017, 1.99, .316, .25, .099)
    part.rounded("Amber", 0, 1.115, .015, 1.99, .335, .26, .090)
    part.rounded("Cream", 0, 1.225, .149, 1.70, .058, .014, .028)
    for x in (-.47, 0, .47):
        part.faceplate("AmberDark", [(x-.105, 1.14), (x-.105, 1.10), (x, 1.037),
                                     (x+.105, 1.10), (x+.105, 1.14), (x, 1.081)], .147, .16)
    part.write("slide")


if __name__ == "__main__":
    MODELS.mkdir(parents=True, exist_ok=True)
    track()
    portal()
    train()
    jump()
    slide()
