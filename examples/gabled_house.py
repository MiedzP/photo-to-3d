# Test model: a gabled house with a centred door. Units: mm. Used to exercise the pipeline
# without an API key:  python -m p23d run examples\refs --size 120 --out runs\house --no-llm --script examples\gabled_house.py
W, D, H = 100.0, 80.0, 60.0      # width (X), depth (Y), wall height (Z)
RIDGE = 30.0                     # roof rise above the walls

walls = Part.makeBox(W, D, H)
roof_profile = Part.Face(Part.makePolygon([      # first point repeated to close the wire
    FreeCAD.Vector(0, 0, H),
    FreeCAD.Vector(W, 0, H),
    FreeCAD.Vector(W / 2, 0, H + RIDGE),
    FreeCAD.Vector(0, 0, H),
]))
roof = roof_profile.extrude(FreeCAD.Vector(0, D, 0))
if roof.Volume < 0:          # extruded solids can come out inside-out; flip them
    roof.reverse()
door = Part.makeBox(16, 4, 30, FreeCAD.Vector(W / 2 - 8, -1, 0))

result = walls.fuse(roof).cut(door).removeSplitter()
