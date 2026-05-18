<img src="https://upload.wikimedia.org/wikipedia/commons/6/68/Logo_universidad_icesi.svg" width="220">

# EcoMarket AI Support — Proyecto Final
## Agente de IA para Automatización de Devoluciones

**Maestría en Inteligencia Artificial · IA Generativa**  
**Integrantes:** Johan Sebastian Bonilla · Edwin Gómez

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/sebastianb92/ecomarket-agent-solution/blob/main/notebooks/EcoMarket_Agent_Solution.ipynb)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![LangChain](https://img.shields.io/badge/LangChain-Agents-green)
![LLM](https://img.shields.io/badge/LLM-LLaMA_3.3_70B-orange)

---

## Descripción

Este proyecto extiende la arquitectura RAG del Taller Práctico #2 incorporando un **Agente de IA** capaz de ejecutar acciones autónomas sobre el sistema de EcoMarket. La tarea automatizada es el proceso completo de devolución de productos.

El agente puede:

- **Consultar** estado de pedidos: tracking, retrasos, cancelaciones.
- **Verificar** si un pedido es elegible para devolución (reglas deterministas: estado, categoría, plazo, daños).
- **Generar** una etiqueta de devolución con código único, transportista y fecha límite.
- **Responder** consultas generales usando la cadena RAG del Taller 2 (RetrievalQA + ChromaDB).

El agente implementa un patrón **Router** con 4 herramientas y un sistema de **action logging** para monitoreo y auditoría.

---

## Arquitectura

```
Usuario (Gradio / Streamlit)
      │
      ▼
Agente LangChain (create_agent — ReAct loop)
      │
      ├── consultar_estado_pedido()             →  DataFrame en tiempo real
      ├── verificar_elegibilidad_devolucion()   →  Reglas deterministas + DataFrame
      ├── generar_etiqueta_devolucion()         →  Código único + fecha límite
      └── consultar_base_conocimiento()         →  RAG (RetrievalQA + ChromaDB + LLM)
      │
      └── _registrar_accion()                   →  logs/agent_actions.jsonl
```

---

## Stack Tecnológico

| Componente | Librería / Modelo |
|---|---|
| Agente | `langchain.agents.create_agent` (LangGraph) |
| Herramientas | `langchain_core.tools.tool` |
| LLM | `llama-3.3-70b-versatile` via Groq API |
| Embeddings | `intfloat/multilingual-e5-large` (HuggingFace, CPU) |
| Vector Store | ChromaDB via `langchain_chroma` |
| Cadena RAG | `langchain_classic.chains.RetrievalQA` |
| Interfaz Notebook | Gradio `gr.ChatInterface` |
| Interfaz Producción | Streamlit (app.py) |

---

## Estructura del Repositorio

```
ecomarket-agent-solution-plus/
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
│   └── EcoMarket_Agent_Solution.ipynb  ← Fases 2 y 4 (código + interfaz Gradio)
│
├── app.py                              ← Interfaz Streamlit (producción)
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Herramientas del Agente

### `consultar_estado_pedido(numero_pedido)`
Consulta el DataFrame en tiempo real para obtener toda la información disponible de un pedido (estado, tracking, fechas, producto, cliente).

### `verificar_elegibilidad_devolucion(pedido_id, motivo)`
Aplica reglas **deterministas** de elegibilidad en este orden:
1. Estado del pedido (solo ENTREGADO y LISTO PARA RECOGIDA son elegibles)
2. Daño en tránsito (aprobación automática con compensación)
3. Categoría del producto (higiene y perecederos no elegibles)
4. Plazo de 30 días desde entrega

### `generar_etiqueta_devolucion(pedido_id)`
Genera etiqueta de devolución con código único, fecha límite (14 días) y transportista según tipo de devolución. **Verifica internamente** que exista una devolución aprobada previamente.

### `consultar_base_conocimiento(pregunta)`
Encapsula la cadena RAG del Taller 2 (RetrievalQA). Responde preguntas generales sobre política de devoluciones, FAQ y estado de pedidos.

---

## Monitoreo

Cada invocación de herramienta queda registrada en `logs/agent_actions.jsonl`:

```json
{
  "timestamp": "2024-07-05T14:32:11.204",
  "session_id": "a3f9b21c",
  "herramienta": "verificar_elegibilidad_devolucion",
  "input": {"pedido_id": "ECO-12347", "motivo": "no me gusta el tamaño"},
  "output": {"elegible": true, "estado": "ENTREGADO"}
}
```

---

## Escenarios de Prueba

| # | Escenario | Herramientas invocadas |
|---|---|---|
| 1 | Estado de pedido (tracking) | `consultar_estado_pedido` |
| 2 | Devolución ELEGIBLE (flujo completo) | `verificar` → `generar_etiqueta` |
| 3 | Devolución NO ELEGIBLE (en tránsito) | `verificar` |
| 4 | Devolución CANCELADO | `verificar` |
| 5 | Devolución por DAÑO (compensación) | `verificar` → `generar_etiqueta` |
| 6 | Consulta general de política | `consultar_base_conocimiento` |
| 7 | Pedido inexistente | `verificar` |
| 8 | Fuera de dominio | Ninguna |
| 9 | Bypass: etiqueta sin verificar | `generar_etiqueta` (falla) |

---

## Ejecución

### Notebook (Gradio)
```bash
# Ejecutar en Jupyter o Colab
jupyter notebook notebooks/EcoMarket_Agent_Solution.ipynb
```

### Streamlit (producción)
```bash
cp .env.example .env  # Configura tus API keys
pip install -r requirements.txt
streamlit run app.py
```

---

## Documentación

`docs/Proyecto_Final_EcoMarket.md` contiene:
- **Fase 1:** Diseño de arquitectura, 4 herramientas, justificación de LangChain, diagrama de flujo.
- **Fase 3:** Matriz de 6 riesgos de seguridad/ética, sistema de monitoreo en 3 capas, 5 propuestas de mejora.

---

## Autores

* Johan Sebastian Bonilla
* Edwin Gómez
