---
title: Map
---

The known world. Explored regions are drawn in; the rest is still fog. Each explored region carries the rumor told about it: the mystery waiting in that direction. Hover a place to see its name, or click it to open its page.

```base
views:
  - type: leaflet-map
    name: Map
    mapName: en
    image: assets/jth-map.svg
    height: 520
    minZoom: -1
    maxZoom: 3
    defaultZoom: 0
    zoomDelta: 0.25
    scale: "1"
    unit: km
    overlay: assets/jth-map-rumors.json
    lang: en
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

The outlined hex with the castle is Marrogate, where every journey begins. The Rumors switch in the map's layer menu hides or shows the rumor labels. Dark hexes are still unexplored.
