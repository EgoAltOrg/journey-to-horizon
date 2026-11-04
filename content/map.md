---
title: Map
---

The known world. Explored regions are drawn in; the rest is still fog. Hover a marker to see the place, or click through to its page.

```base
views:
  - type: leaflet-map
    name: Map
    image: assets/jth-map.svg
    height: 520
    minZoom: -1
    maxZoom: 3
    defaultZoom: 0
    zoomDelta: 0.25
    scale: "1"
    unit: km
```

## Map key

Each hex shows its biome, and the dots under the symbol show how hard it is to cross.

### Biomes

|  | Biome | What you'll find |
|---|---|---|
| ![[legend-underground.svg]] | Underground | caves, mines, fungal forests |
| ![[legend-aquatic.svg]] | Aquatic | lake, sea, reef, delta |
| ![[legend-wetlands.svg]] | Wetlands | swamp, marsh, bog, fen |
| ![[legend-grasslands.svg]] | Grasslands | plains, veldt, savannah |
| ![[legend-tropical.svg]] | Tropical | jungle, rainforest, mangrove |
| ![[legend-forest.svg]] | Forest | deciduous, evergreen, coniferous |
| ![[legend-drylands.svg]] | Drylands | desert, canyon, prairie, salt flat |
| ![[legend-rolling.svg]] | Rolling | hills, chaparral, moor, heath |
| ![[legend-mountain.svg]] | Mountain | plateau, montane, alpine |
| ![[legend-frozen.svg]] | Frozen | tundra, taiga, glacier |
| ![[legend-badlands.svg]] | Badlands | volcano, crystalline, barren |

### Terrain dots

|  | Terrain | Days to enter |
|---|---|---|
| ![[legend-dots-1.svg]] | **Optimal:** paved roads, highways, raised paths | about 1 |
| ![[legend-dots-2.svg]] | **Fair:** trade roads, caravan paths, wilderness trails | about 2 |
| ![[legend-dots-3.svg]] | **Rough:** narrow tracks, game trails, tangled undergrowth, easy to get lost | about 3 |
| ![[legend-dots-4.svg]] | **Extreme:** cliffs, quagmires, collapsing ground, trackless wilds | about 4 |

More dots also means more chances of running into trouble along the way.

### Other marks

|  | Mark | Meaning |
|---|---|---|
| ![[legend-blight.svg]] | Red ✗ | Shadowblight: corrupted land, dangerous to cross |

The pale hex with no symbol is Marrogate, where every journey begins. Dark hexes are still unexplored.
