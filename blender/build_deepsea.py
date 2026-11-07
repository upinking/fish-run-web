"""Build the subsea station modules using the same GLTF axis and rail pitch.

Run: Blender --background --factory-startup --python blender/build_deepsea.py
The tile begins at z=0 and extends to z=-40. The airlock sits on a tile seam.
"""
import sys
from math import sin
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_station import LANES, LENGTH, MODELS, PALETTE, Parts, arch_ring


PALETTE.update({
    "DeepBed": ("2A4361", .03, .81),
    "DeepPanel": ("718BA8", .04, .58),
    "DeepIvory": ("C1D9E8", .06, .47),
    "DeepNavy": ("243555", .12, .48),
    "DeepTeal": ("336D87", .12, .41),
    "DeepCyan": ("2BC8F3", .02, .29, 1.0, .66),
    "DeepAqua": ("94F5EE", .02, .32, 1.0, .64),
    "DeepViolet": ("AC99F5", .01, .32, 1.0, .52),
    "DeepGlass": ("63CBEA", .09, .25, .14),
    "DeepGlassRoof": ("8FDBF1", .08, .21, .095),
    "DeepGraphite": ("1C2D49", .04, .72),
    "DeepReef": ("2A6177", 0, .93),
    "DeepKelp": ("2B806C", 0, .84),
    "DeepKelpLight": ("6AAB77", 0, .79),
    "DeepFish": ("A7DFE9", .04, .48, 1.0, .14),
})


def tube_outline(half_width, shoulder, roof, foot=.16):
    """A glass tube profile with shallow chamfers above the side windows."""
    rise = roof - shoulder
    curve = [
        (-half_width, foot),
        (-half_width, shoulder),
        (-half_width * .984, shoulder + rise * .27),
        (-half_width * .942, shoulder + rise * .52),
        (-half_width * .877, shoulder + rise * .73),
        (-half_width * .794, shoulder + rise * .90),
        (-half_width * .692, shoulder + rise * .98),
        (-half_width * .58, roof),
        (0, roof),
    ]
    return curve + [(-x, y) for x, y in reversed(curve[:-1])]


def rails(part):
    part.box("DeepBed", 0, -.25, -20, 8.12, .4, LENGTH)
    for lane in LANES:
        part.box("DeepPanel", lane, -.068, -20, 2.22, .135, LENGTH)
        part.box("DeepBed", lane, -.009, -20, 1.82, .018, LENGTH)
        for i in range(50):
            z = -.4 - i * .8
            part.box("DeepPanel", lane, .016, z, 1.81, .044, .235)
            for offset in (-.68, .68):
                part.box("RailWeb", lane + offset, .040, z, .153, .022, .155)
        for offset in (-.68, .68):
            x = lane + offset
            part.box("RailWeb", x, .051, -20, .075, .057, LENGTH)
            part.box("RailFace", x, .084, -20, .107, .022, LENGTH)


def server(part, x, z, side, accent):
    """One bank, with inlet grilles facing the runner and cool side strips."""
    height = 2.22
    part.rounded("DeepNavy", x, .28 + height / 2, z, .88, height, 1.45, .12)
    part.rounded("DeepIvory", x, .29 + height / 2, z + .733, .80, height - .14, .10, .094)
    part.rounded("DeepGraphite", x, 1.385, z + .797, .64, 1.90, .054, .062)
    part.rounded(accent, x, 2.234, z + .832, .39, .048, .015, .02)
    for level in range(5):
        y = .625 + .299 * level
        part.box("DeepTeal", x, y, z + .831, .54, .218, .025)
        part.box("DeepPanel", x - .073, y, z + .848, .30, .035, .012)
        part.box(accent, x + .162, y, z + .849, .070, .034, .015)
        part.box("DeepAqua", x + .228, y, z + .849, .025, .025, .015)
    part.box("DeepGraphite", x - side * .453, 1.40, z - .055, .034, 1.76, 1.14)
    for level in range(5):
        y = .74 + .29 * level
        part.box("DeepTeal", x - side * .477, y, z - .055, .016, .17, .99)
        part.box("DeepCyan", x - side * .487, y, z + .068, .014, .043, .53)
        part.box(accent, x - side * .487, y, z - .332, .014, .036, .057)
    part.box("DeepIvory", x - side * .477, 1.40, z + .557, .025, 1.74, .055)
    part.box("DeepIvory", x, .33, z, 1.06, .14, 1.67)


def side_aisles(part):
    for side in (-1, 1):
        part.box("DeepPanel", side * 5.99, -.075, -20, 3.9, .61, LENGTH)
        part.box("DeepTeal", side * 4.055, -.025, -20, .15, .43, LENGTH)
        part.box("DeepIvory", side * 4.09, .229, -20, .24, .05, LENGTH)
        part.box("Tactile", side * 4.319, .258, -20, .042, .013, LENGTH)
        part.box("RailFace", side * 4.77, .761, -20, .057, .057, LENGTH)
        for index in range(20):
            z = -1 - index * 2
            color = "DeepIvory" if index % 3 == 0 else "DeepPanel"
            part.box(color, side * 5.98, .235, z, 3.53, .029, 1.977)
            if index % 2 == 0:
                part.box("DeepTeal", side * 4.77, .497, z, .054, .50, .054)
                part.box("WarmLight", side * 4.038, .152, z, .026, .043, .28)
        for index in range(4):
            z = -4.3 - index * 10 - (1.35 if side == 1 else 0)
            accent = "DeepViolet" if (index + (side == 1)) % 2 == 0 else "DeepCyan"
            server(part, side * 6.22, z, side, accent)
            server(part, side * 6.22, z - 1.95, side, accent)
        part.box("DeepNavy", side * 7.805, .365, -20, .27, .64, LENGTH)
        part.box("DeepTeal", side * 7.810, 2.37, -20, .142, .085, LENGTH)
        part.box("DeepCyan", side * 7.655, .62, -20, .04, .046, LENGTH)


def arch_face(part, material, outer, inner, z, front):
    """A face-mounted accent. The pressure rib owns the inner and outer walls."""
    n = len(outer)
    vertices = [(x, y, z) for x, y in outer + inner]
    faces = [(i, n + i, n + i + 1, i + 1) for i in range(n - 1)]
    if not front:
        faces = [face[::-1] for face in faces]
    part.mesh(material, vertices, faces)


def shell(part):
    shell_profile = tube_outline(7.85, 3.71, 6.63, foot=.62)
    for cell in range(4):
        front = -.418 - cell * 10
        back = max(-LENGTH, front - 9.642)
        for index in range(len(shell_profile) - 1):
            a, b = shell_profile[index:index + 2]
            material = "DeepGlass" if index in (0, len(shell_profile) - 2) else "DeepGlassRoof"
            part.mesh(material, [(a[0], a[1], back), (b[0], b[1], back),
                                 (b[0], b[1], front), (a[0], a[1], front)], [(0, 1, 2, 3)])

    outside = tube_outline(7.945, 3.78, 6.77)
    middle = tube_outline(7.68, 3.69, 6.48)
    inside = tube_outline(7.53, 3.64, 6.30)
    line = tube_outline(7.58, 3.66, 6.36)
    for i in range(4):
        z = -.25 - i * 10
        arch_ring(part, "DeepNavy", outside, inside, z - .214, z + .214)
        for face in (-1, 1):
            arch_face(part, "DeepPanel", middle, inside, z + face * .228, face > 0)
            arch_face(part, "DeepCyan", line, inside, z + face * .243, face > 0)
        light_z = min(z, -.285)
        part.rounded("DeepNavy", 0, 6.300, light_z, 2.35, .159, .57, .076, n=3)
        part.rounded("WarmLight", 0, 6.260, light_z, 2.13, .118, .522, .057, n=3)
        for side in (-1, 1):
            part.box("DeepNavy", side * 7.67, .40, z, .46, .80, .63 if i else .45)
            part.rounded("WarmLight", side * 7.615, 2.20, min(z + .251, -.014),
                         .089, 1.09, .025, .042, n=3)
    for side in (-1, 1):
        for x, y in ((2.38, 6.609), (4.55, 6.609), (6.22, 6.318)):
            part.box("DeepNavy", side * x, y, -20, .112, .108, LENGTH)


def ribbon(part, material, path):
    """An underwater frond with one strip of geometry visible from both sides."""
    vertices = [(x + side * width, y, z)
                for x, y, z, width in path for side in (-1, 1)]
    faces = [(i, i + 1, i + 3, i + 2) for i in range(0, len(vertices) - 2, 2)]
    part.mesh(material, vertices, faces, smooth=True)
    part.mesh(material, vertices, [face[::-1] for face in faces], smooth=True)


def kelp(part, x, z, height, phase):
    def stem(t):
        return x + .37 * sin(t * 7 + phase) * t, -3.15 + t * height, z + .4 * sin(t * 4 + phase) * t

    ribbon(part, "DeepKelp", [(*stem(i / 9), .11 - .093 * i / 9) for i in range(10)])
    for i in range(5):
        t = .31 + .122 * i
        sx, sy, sz = stem(t)
        lean = (-1 if i % 2 else 1) * (.72 - .05 * i)
        rise = (1.31 - .13 * i) * height / 10
        leaf = [(sx, sy, sz, .035),
                (sx + lean * .55, sy + rise * .31, sz + .07, .22 - .021 * i),
                (sx + lean, sy + rise * .72, sz + .18, .15 - .015 * i),
                (sx + lean * .82, sy + rise, sz + .29, .009)]
        ribbon(part, "DeepKelpLight" if i % 2 else "DeepKelp", leaf)


def outside_life(part):
    # All vegetation is beyond the side glazing, with clear stretches between clusters.
    for side in (-1, 1):
        for i, z in enumerate((-7.2, -19.0, -33.2)):
            z -= 2 if side > 0 else 0
            x = side * (9.7 + .74 * i)
            part.ellipsoid("DeepReef", x + side * .9, -3.10, z, 2.25, 1.48, 2.02, n=8, bands=4)
            part.ellipsoid("DeepReef", x + side * 3.1, -2.92, z - 1.4, 1.73, 2.12, 2.53, n=7, bands=4)
            kelp(part, x, z, 9.0 + .77 * i, i + side)
            kelp(part, x + side * 1.17, z - 1.4, 8.34 + .43 * i, i - side)

    # A small staggered school reads through the left windows at runner height.
    for x, y, z, size in ((-10.04, 3.81, -15.00, .38), (-11.41, 4.37, -16.53, .30),
                          (-10.90, 3.31, -16.88, .27), (-11.88, 3.76, -17.50, .33),
                          (-12.98, 3.52, -17.89, .29), (-12.37, 4.68, -18.72, .23)):
        part.ellipsoid("DeepFish", x, y, z, size, size * .32, size * .26, n=8, bands=4)
        part.faceplate("DeepFish", [(x - size * 1.43, y - size * .29),
                                    (x - size * .70, y),
                                    (x - size * 1.43, y + size * .29)], z - .022, z + .022)


def deepsea_track():
    part = Parts()
    rails(part)
    side_aisles(part)
    shell(part)
    outside_life(part)
    part.write("deepsea-track")


def deepsea_portal():
    part = Parts()
    outer = tube_outline(8.08, 3.92, 7.03)
    middle = tube_outline(7.72, 3.80, 6.64)
    inner = tube_outline(7.39, 3.67, 6.28)
    trim = tube_outline(7.47, 3.72, 6.41)
    arch_ring(part, "DeepNavy", outer, inner, -1.66, .43)
    for face, z in ((-1, -1.66), (1, .43)):
        arch_face(part, "DeepTeal", outer, middle, z + face * .015, face > 0)
        arch_face(part, "DeepPanel", middle, inner, z + face * .015, face > 0)
        arch_face(part, "DeepCyan", trim, inner, z + face * .033, face > 0)
    for side in (-1, 1):
        x = side * 7.72
        part.box("DeepNavy", x, .47, -.38, .70, .93, 2.1)
        part.rounded("DeepGraphite", x, 1.46, .478, .29, 1.15, .09, .077)
        part.rounded("DeepViolet", x, 1.68, .531, .09, .47, .025, .043)
        part.rounded("DeepAqua", x, 1.19, .531, .09, .29, .025, .043)

    # An illuminated stack emblem marks the server station above the passage.
    part.rounded("DeepNavy", 0, 6.81, .50, 2.48, .49, .18, .16)
    part.rounded("DeepIvory", 0, 6.81, .603, 2.24, .352, .041, .12)
    part.rounded("DeepTeal", 0, 6.81, .631, 1.95, .255, .022, .098)
    for x in (-.50, 0, .50):
        part.rounded("DeepCyan", x, 6.81, .650, .30, .11, .018, .035)
    part.write("deepsea-portal")


if __name__ == "__main__":
    MODELS.mkdir(parents=True, exist_ok=True)
    deepsea_track()
    deepsea_portal()
