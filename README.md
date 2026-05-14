<img src="https://upload.wikimedia.org/wikipedia/commons/6/68/Logo_universidad_icesi.svg" width="220">

# EcoMarket AI Support — Proyecto Final
## Agente de IA para Automatización de Devoluciones

**Maestría en Inteligencia Artificial · IA Generativa**  
**Integrantes:** Johan Sebastian Bonilla · Edwin Gómez

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/sebastianb92/ecomarket-agent-solution/blob/main/notebooks/EcoMarket_Agent_Solution.ipynb)

---

## Descripción

Este proyecto extiende la arquitectura RAG del Taller Práctico #2 incorporando un **Agente de IA** capaz de ejecutar acciones autónomas sobre el sistema de EcoMarket.

A diferencia del sistema RAG anterior (puramente consultivo), este agente puede:

- **Verificar** si un pedido es elegible para devolución consultando el sistema en tiempo real.
- **Generar** una etiqueta de devolución con número de autorización RMA y fecha límite de envío.
- **Responder** consultas generales usando la cadena RAG del Taller 2 como herramienta adicional.

El agente implementa un patrón **Router**: analiza la intención del usuario y decide qué herramienta invocar en cada caso.

---

## Arquitectura

```
Usuario (Gradio)
      │
      ▼
Agente LangChain (create_agent)
      │
      ├── verificar_elegibilidad_devolucion()  →  Excel en tiempo real
      ├── generar_etiqueta_devolucion()        →  Genera RMA simulado
      └── consultar_base_conocimiento()        →  RAG (ChromaDB + LLM)
```

---

## Stack Tecnológico

| Componente | Librería / Modelo |
|---|---|
| Agente | `langchain.agents.create_agent` |
| Herramientas | `langchain_core.tools.tool` |
| LLM | `llama-3.3-70b-versatile` via Groq API |
| Embeddings | `intfloat/multilingual-e5-large` (HuggingFace, CPU) |
| Vector Store | ChromaDB via `langchain_chroma` |
| Cadena RAG | `langchain_classic.chains.RetrievalQA` |
| Interfaz | Gradio `gr.Blocks` |

---

## Estructura del Repositorio

```
ecomarket-agent-solution/
│
├── data/
│   ├── FAQ.json
│   ├── POLÍTICA DE DEVOLUCIONES.pdf
│   └── pedidos_ecomarket.xlsx
│
├── docs/
│   └── Proyecto_Final_EcoMarket.md     ← Fases 1 y 3 (diseño + análisis crítico)
│
├── notebooks/
│   └── EcoMarket_Agent_Solution.ipynb  ← Fases 2 y 4 (código + interfaz)
│
├── requirements.txt
└── README.md
```

---

## Herramientas del Agente

### `verificar_elegibilidad_devolucion(pedido_id)`
Consulta el DataFrame de pedidos en tiempo real y aplica reglas **deterministas** de elegibilidad basadas en la política oficial de EcoMarket. La decisión no depende del LLM, lo que garantiza consistencia y previene alucinaciones.

Estados elegibles: `ENTREGADO`, `LISTO PARA RECOGIDA`

### `generar_etiqueta_devolucion(pedido_id)`
Genera una etiqueta de devolución simulada con número de autorización RMA único, fecha límite de envío (10 días hábiles) y centro de devolución asignado según el transportista. Verifica internamente la elegibilidad antes de proceder.

### `consultar_base_conocimiento(pregunta)`
Encapsula la cadena RAG del Taller 2. Responde preguntas generales sobre política de devoluciones, FAQ y estado de pedidos sin intención de devolución.

---

## Instalación y Uso

### Opción 1 — Google Colab (recomendado)

Haz clic en el badge **Open in Colab** al inicio de este README. Solo necesitas configurar tu API key de Groq en los Secrets de Colab:

```
Colab → Ícono de llave (🔑) → Agregar secreto
Nombre: GROQ_API_KEY
Valor:  tu_api_key_aquí
```

### Opción 2 — Local

```bash
# 1. Clonar el repositorio
git clone https://github.com/sebastianb92/ecomarket-agent-solution.git
cd ecomarket-agent-solution

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variable de entorno
echo "GROQ_API_KEY=tu_api_key_aquí" > .env

# 4. Abrir el notebook
jupyter notebook notebooks/EcoMarket_Agent_Solution.ipynb
```

### Obtener API Key de Groq

1. Regístrate en [console.groq.com](https://console.groq.com)
2. Ve a **API Keys** → **Create API Key**
3. Copia la key generada

---

## Escenarios de Prueba

El notebook incluye 7 pruebas que cubren los casos principales:

| # | Escenario | Herramientas invocadas |
|---|---|---|
| 1 | Devolución con pedido **ELEGIBLE** | `verificar` → `generar_etiqueta` |
| 2 | Devolución con pedido **EN TRÁNSITO** | `verificar` |
| 3 | Devolución con pedido **CANCELADO** | `verificar` |
| 4 | Consulta general de política | `consultar_base_conocimiento` |
| 5 | Estado de pedido sin devolución | `consultar_base_conocimiento` |
| 6 | Pedido **inexistente** | `verificar` |
| 7 | Consulta fuera de dominio | `consultar_base_conocimiento` |

---

## Monitoreo

Cada invocación de herramienta queda registrada en `logs/agent_actions.jsonl` con el siguiente formato:

```json
{
  "timestamp": "2024-07-05T14:32:11.204",
  "session_id": "a3f9b21c",
  "herramienta": "verificar_elegibilidad_devolucion",
  "input": {"pedido_id": "ECO-12347"},
  "output": {"elegible": true, "estado": "ENTREGADO", ...}
}
```

---

## Documentación

El archivo `docs/Proyecto_Final_EcoMarket.md` contiene:

- **Fase 1:** Diseño de arquitectura, definición de herramientas, justificación de LangChain y diagrama de flujo del agente.
- **Fase 3:** Análisis de riesgos éticos y de seguridad, sistema de monitoreo en tres capas y propuestas de mejora.

---

## Relación con el Taller 2

Este proyecto es una extensión directa del repositorio [`ecomarket-solution`](https://github.com/sebastianb92/ecomarket-solution). Se reutilizan sin modificación:

- El LLM (`ChatGroq` con `llama-3.3-70b-versatile`)
- Los embeddings (`multilingual-e5-large`)
- El vector store (ChromaDB)
- La cadena RAG (`RetrievalQA`) — ahora como Herramienta 3 del agente

---

## Licencia

Proyecto académico — Maestría en Inteligencia Artificial, Universidad Icesi.
