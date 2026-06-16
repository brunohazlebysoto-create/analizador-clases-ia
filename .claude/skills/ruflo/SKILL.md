---
name: ruflo
description: "Orquestación multi-agente para el Analizador de Clases IA usando el framework Ruflo. Proporciona metodología SPARC, coordinación de agentes especializados, verificación de calidad y flujos de trabajo automatizados para desarrollo, testing y análisis del proyecto. Úsalo cuando necesites coordinar múltiples agentes, aplicar TDD, refactorizar código con metodología estructurada o automatizar pipelines de CI/CD."
---

# Ruflo — Meta-Harness de Agentes para Analizador de Clases IA

> Framework basado en [ruvnet/ruflo](https://github.com/ruvnet/ruflo): orquesta agentes IA especializados para desarrollo, análisis y calidad del código.

## Inicio Rápido

```bash
# Instalación del CLI de Ruflo (opcional)
npx ruflo@alpha init

# O usar directamente desde Claude Code con este skill
/ruflo <modo> [opciones]
```

## Modos Disponibles

### Desarrollo y Arquitectura

| Modo | Descripción |
|------|-------------|
| `sparc` | Metodología SPARC completa (Spec → Pseudocode → Architecture → Refinement → Completion) |
| `architect` | Diseño de arquitectura del sistema |
| `coder` | Implementación de código con mejores prácticas |
| `tdd` | Desarrollo guiado por pruebas (Red → Green → Refactor) |
| `refactor` | Refactorización estructurada de código existente |

### Análisis e Inteligencia

| Modo | Descripción |
|------|-------------|
| `researcher` | Investigación profunda de tecnologías y patrones |
| `analyzer` | Análisis de código, rendimiento y arquitectura |
| `optimizer` | Optimización de performance y recursos |
| `debugger` | Diagnóstico y resolución de bugs |

### Orquestación y Coordinación

| Modo | Descripción |
|------|-------------|
| `orchestrator` | Coordinación de múltiples agentes en paralelo |
| `swarm` | Enjambre de agentes con topología mesh/jerárquica |
| `workflow` | Flujos de trabajo automatizados multi-paso |
| `pair` | Programación en pareja IA-asistida |

### Calidad y Verificación

| Modo | Descripción |
|------|-------------|
| `verify` | Verificación de calidad con truth scoring (0.0–1.0) |
| `review` | Revisión de código con análisis de seguridad |
| `test-gen` | Generación automática de tests |
| `docs` | Generación de documentación técnica |

---

## Metodología SPARC

El modo estrella de Ruflo aplica el ciclo completo de 5 fases:

```
1. Specification   → Definir requisitos y casos de uso
2. Pseudocode      → Diseñar la lógica antes de implementar
3. Architecture    → Planificar componentes y dependencias
4. Refinement      → Implementar con TDD y revisión continua
5. Completion      → Integrar, documentar y desplegar
```

**Ejemplo de uso para este proyecto:**

```
/ruflo sparc "Agregar soporte para videos de YouTube como fuente de entrada"
```

Esto desplegará agentes especializados para:
- Definir los requisitos de integración con YouTube API
- Diseñar la arquitectura del módulo de descarga
- Implementar con cobertura de tests ≥ 90%
- Documentar la nueva funcionalidad

---

## Flujos de Trabajo Específicos para este Proyecto

### Análisis de Video Pipeline

```bash
# Orquestar agentes para mejorar el pipeline de extracción de slides
/ruflo workflow "Optimizar detección de cambios de diapositiva"

# Agentes involucrados:
# → analyzer: Analiza el algoritmo actual en video_processor.py
# → optimizer: Propone mejoras de rendimiento
# → tdd: Implementa con tests de regresión
# → docs: Actualiza documentación
```

### Integración de APIs de IA

```bash
# Agregar soporte para nuevos modelos de IA
/ruflo architect "Diseñar capa de abstracción para múltiples providers de IA"

# Refactorizar servicios existentes
/ruflo refactor gemini_service.py groq_service.py --pattern="service-layer"
```

### Verificación de Calidad

```bash
# Ejecutar verificación completa del proyecto
/ruflo verify --threshold=0.95

# Generar suite de tests
/ruflo test-gen video_processor.py --coverage=90

# Revisión de seguridad
/ruflo review --security --owasp
```

---

## Configuración de Agentes

Ruflo soporta múltiples topologías de coordinación:

```json
{
  "orchestration": {
    "topology": "hierarchical",
    "max_agents": 10,
    "consensus": true
  },
  "memory": {
    "type": "vector",
    "backend": "hnsw",
    "persistence": true
  },
  "quality": {
    "truth_threshold": 0.95,
    "auto_rollback": true,
    "coverage_minimum": 80
  }
}
```

### Topologías de Swarm

- **Jerárquica**: Orchestrator → Agentes especializados (ideal para tareas secuenciales)
- **Mesh**: Todos los agentes se comunican entre sí (ideal para análisis paralelo)
- **Adaptativa**: Cambia topología según la complejidad de la tarea

---

## Truth Scoring — Sistema de Calidad

Ruflo evalúa la calidad de outputs con puntuaciones de 0.0 a 1.0:

| Rango | Estado | Acción |
|-------|--------|--------|
| 0.98 – 1.00 | ⭐ Excelente | Aprobar automáticamente |
| 0.95 – 0.97 | ✅ Bueno | Aprobar con revisión |
| 0.90 – 0.94 | ⚠️ Advertencia | Revisión manual requerida |
| < 0.90 | ❌ Crítico | Rollback automático |

```bash
# Ver puntuaciones actuales
/ruflo truth

# Revertir al último estado válido
/ruflo verify rollback --last-good
```

---

## Integración con el Proyecto

### Variables de Entorno

```bash
# Configurar APIs para Ruflo
RUFLO_MODEL=claude-sonnet-4-6
RUFLO_MAX_AGENTS=5
RUFLO_MEMORY_BACKEND=hnsw
RUFLO_TRUTH_THRESHOLD=0.95

# APIs del proyecto (ya configuradas)
GROQ_API_KEY=<tu-clave>
GEMINI_API_KEY=<tu-clave>
```

### Comandos de Desarrollo Rápido

```bash
# Análisis completo del proyecto
/ruflo analyzer --full-scan

# Generar plan de mejoras
/ruflo researcher "Mejores prácticas para análisis de video con IA en 2025"

# Pair programming para nueva feature
/ruflo pair --mode=navigator "Implementar exportación a PDF"

# Optimizar rendimiento del batch processing
/ruflo optimizer gemini_service.py --focus=api-efficiency
```

---

## Recursos

- **Repositorio**: [github.com/ruvnet/ruflo](https://github.com/ruvnet/ruflo)
- **CLI**: `npx ruflo@alpha --help`
- **Web UI**: flo.ruv.io
- **Goal Planner**: goal.ruv.io
- **Licencia**: MIT

---

## Notas de Integración

> Este skill adapta las capacidades del framework Ruflo al contexto específico del
> **Analizador de Clases IA** — un pipeline Python/Streamlit que extrae diapositivas
> de videos educativos, transcribe audio con Groq Whisper y sintetiza explicaciones
> con Google Gemini.
>
> Los modos de Ruflo más útiles para este proyecto son: `sparc`, `analyzer`,
> `optimizer`, `tdd` y `pair`.
