---
title: Mapa
---

O mundo conhecido. As regiões exploradas estão desenhadas; o resto ainda é névoa. Cada região explorada mostra o rumor que se conta sobre ela: o mistério que espera nessa direção. Passa o rato por cima de um lugar para ver o nome, ou clica para ir à sua página.

```base
views:
  - type: leaflet-map
    name: Map
    mapName: pt
    image: assets/jth-map.svg
    height: 520
    minZoom: -1
    maxZoom: 3
    defaultZoom: 0
    zoomDelta: 0.25
    scale: "1"
    unit: km
    overlay: assets/jth-map-rumors.json
    lang: pt
```

## Legenda do mapa

Cada hex mostra o seu bioma, e os pontos por baixo do símbolo mostram quão difícil é atravessá-lo.

### Biomas

|  | Bioma | O que vais encontrar |
|---|---|---|
| ![[legend-underground.svg]] | Underground | grutas, minas, florestas de fungos |
| ![[legend-aquatic.svg]] | Aquatic | lago, mar, recife, delta |
| ![[legend-wetlands.svg]] | Wetlands | pântano, paul, turfeira, charco |
| ![[legend-grasslands.svg]] | Grasslands | planícies, estepe, savana |
| ![[legend-tropical.svg]] | Tropical | selva, floresta tropical, mangal |
| ![[legend-forest.svg]] | Forest | caducifólia, perene, de coníferas |
| ![[legend-drylands.svg]] | Drylands | deserto, desfiladeiro, pradaria, salina |
| ![[legend-rolling.svg]] | Rolling | colinas, matagal, charneca, urzal |
| ![[legend-mountain.svg]] | Mountain | planalto, serra, alta montanha |
| ![[legend-frozen.svg]] | Frozen | tundra, taiga, glaciar |
| ![[legend-badlands.svg]] | Badlands | vulcão, cristal, terra estéril |

### Pontos de terreno

|  | Terreno | Dias para entrar |
|---|---|---|
| ![[legend-dots-1.svg]] | **Ótimo:** estradas pavimentadas, calçadas, caminhos elevados | cerca de 1 |
| ![[legend-dots-2.svg]] | **Razoável:** estradas de comércio, rotas de caravanas, trilhos | cerca de 2 |
| ![[legend-dots-3.svg]] | **Difícil:** veredas estreitas, trilhos de caça, mato cerrado, fácil perderes-te | cerca de 3 |
| ![[legend-dots-4.svg]] | **Extremo:** falésias, lamaçais, chão que desaba, ermos sem caminho | cerca de 4 |

Mais pontos também querem dizer mais hipóteses de encontrares problemas pelo caminho.

### Outras marcas

|  | Marca | Significado |
|---|---|---|
| ![[legend-blight.svg]] | ✗ vermelho | Shadowblight: terra corrompida, perigosa de atravessar |

O hex com contorno e o castelo é Marrogate, onde começa cada jornada. O interruptor Rumores, no menu de camadas do mapa, esconde ou mostra os rumores. Os hexes escuros ainda estão por explorar.
