# Perfil de localización es-ES

Este perfil define un español técnico neutro para estudiantes y profesionales de software de
distintas regiones. No es un diccionario de sustituciones. La traducción debe conservar la idea,
el nivel técnico y la secuencia pedagógica sin imitar la sintaxis inglesa.

## Criterio editorial

Use frases directas y conectores naturales. Evite cadenas de sustantivos, aperturas repetidas,
eslóganes y calcos que obliguen a releer. Mantenga nombres de producto, código, identificadores,
URLs, prompts de modelo y títulos bibliográficos en su forma canónica.

Las fuentes públicas de NVIDIA en España y Latinoamérica fijan términos como `agentes de IA`,
`razonar, planificar y actuar` y `Generación Aumentada por Recuperación`. La documentación técnica
de Microsoft y AWS ayuda con `límites de confianza`, `llamadas a herramientas`, `entrada no
confiable` y `base de conocimientos`. Cuando las fuentes difieren por región, prefiera la forma
clara en más países y registre la decisión en `profile.json`.

## Figuras y validación

El texto visible y accesible de los SVG también se traduce. Conserve la geometría no textual,
revise los diagramas renderizados en temas claro y oscuro, y compruebe recortes, solapamientos y
ritmo visual en anchos de escritorio y móvil. Una etiqueta puede abreviarse sin perder el concepto.

La validación estática bloquea texto inglés evidente, calcos conocidos, títulos bibliográficos
traducidos, cambios en código o estructura, hashes obsoletos y SVG sin marca de idioma. No puede
certificar naturalidad. Lea cada bloque completo en Localization Studio antes de aceptar el hash.

`shell_translations.json` traduce las preguntas y los encuadres de detalle. Durante el build,
`locale_projection.py` combina esas traducciones y el contenido revisado con la estructura completa
de la página inglesa actual. Si aparece un nuevo control sin traducción, la validación debe fallar.

```bash
python3 scripts/validation/localization_audit.py --locale es-ES
python3 scripts/validation/localization_audit.py --self-test
python3 scripts/translate/translate_svg_text.py --locale es-ES web/nemoclaw/assets/figures/FIGURA.svg --no-api
```
