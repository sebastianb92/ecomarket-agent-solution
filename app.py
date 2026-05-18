"""
EcoMarket AI Agent — Interfaz Web con Streamlit
Proyecto Final: Implementación de un Agente de IA para Automatización de Tareas

Autores: Johan Sebastian Bonilla · Edwin Gómez
"""

import os
import json
import uuid
import hashlib
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_community.vectorstores.utils import filter_complex_metadata
from langchain_community.document_loaders import DataFrameLoader, PyPDFLoader, JSONLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langchain.agents import create_agent
from langchain_classic.chains import RetrievalQA

# ─────────────────────────────────────────────────────────────────────────────
# Configuración de la página
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="EcoBot — Asistente EcoMarket",
    page_icon="🌿",
    layout="centered"
)

st.markdown("""
<style>
    .main-header { text-align: center; padding: 1rem 0; }
    .stTextInput > div > div > input { border: 2px solid #4caf50; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Action Logging
# ─────────────────────────────────────────────────────────────────────────────

LOG_PATH = Path("logs")
LOG_PATH.mkdir(exist_ok=True)

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]


def _registrar_accion(herramienta: str, inputs: dict, outputs: dict) -> None:
    entrada = {
        "timestamp": datetime.now().isoformat(),
        "session_id": st.session_state.session_id,
        "herramienta": herramienta,
        "input": inputs,
        "output": outputs,
    }
    with open(LOG_PATH / "agent_actions.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entrada, ensure_ascii=False) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# Inicialización (cached)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource
def inicializar_sistema():
    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        st.error("⚠️ No se encontró GROQ_API_KEY. Configúrala en un archivo .env")
        st.stop()

    llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=api_key, temperature=0.3)

    embeddings = HuggingFaceEmbeddings(
        model_name="intfloat/multilingual-e5-large",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    vector_store = Chroma(
        collection_name="ecomarket_agent_collection",
        embedding_function=embeddings,
        persist_directory="./chroma_agent_db",
    )

    DATA_DIR = Path(__file__).parent / "data"
    if not DATA_DIR.exists():
        DATA_DIR = Path("data")

    # Indexar solo si vacío
    if vector_store._collection.count() == 0:
        docs = []
        excel_path = DATA_DIR / "pedidos_ecomarket.xlsx"
        if excel_path.exists():
            df = pd.read_excel(excel_path)
            df["contenido"] = df.apply(lambda row: " | ".join(str(v) for v in row), axis=1)
            docs.extend(DataFrameLoader(df, page_content_column="contenido").load())

        pdf_path = DATA_DIR / "POLÍTICA DE DEVOLUCIONES.pdf"
        if pdf_path.exists():
            docs.extend(PyPDFLoader(str(pdf_path)).load())

        json_path = DATA_DIR / "FAQ.json"
        if json_path.exists():
            docs.extend(JSONLoader(
                file_path=str(json_path),
                jq_schema='.faq[] | "Categoría: \\(.categoria)\\nPregunta: \\(.pregunta)\\nRespuesta: \\(.respuesta)"',
                text_content=True,
            ).load())

        if docs:
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200, add_start_index=True)
            splits = filter_complex_metadata(splitter.split_documents(docs))
            vector_store.add_documents(documents=splits)

    retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 3})

    # RAG chain
    rag_prompt = ChatPromptTemplate.from_messages([
        ("system", "Eres EcoBot, asistente de EcoMarket. Usa SOLO el contexto. NO inventes. Responde en español. Sé conciso."),
        ("human", "Contexto:\n{context}\n\nPregunta:\n{question}"),
    ])
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm, retriever=retriever, chain_type="stuff",
        chain_type_kwargs={"prompt": rag_prompt},
    )

    # Pedidos DataFrame
    df_pedidos = pd.read_excel(DATA_DIR / "pedidos_ecomarket.xlsx") if (DATA_DIR / "pedidos_ecomarket.xlsx").exists() else pd.DataFrame()

    return llm, qa_chain, df_pedidos


def crear_agente(llm, qa_chain, df_pedidos):
    if "devoluciones_aprobadas" not in st.session_state:
        st.session_state.devoluciones_aprobadas = {}

    devoluciones_aprobadas = st.session_state.devoluciones_aprobadas

    PRODUCTOS_HIGIENE = ["jabón", "shampoo", "champú", "desodorante", "crema", "gel", "pasta dental"]
    PRODUCTOS_PERECEDEROS = ["frutos secos", "alimento", "comida", "snack", "orgánico comestible", "té", "infusión"]

    @tool
    def consultar_estado_pedido(numero_pedido: str) -> str:
        """Consulta el estado actual de un pedido de EcoMarket.
        Usa cuando el usuario pregunte por estado, tracking o información de un pedido.
        Args:
            numero_pedido: Identificador del pedido, por ejemplo ECO-12345.
        """
        numero_pedido = numero_pedido.strip().upper()
        fila = df_pedidos[df_pedidos["pedido_id"].str.upper() == numero_pedido]
        if fila.empty:
            resultado = {"encontrado": False, "mensaje": f"No se encontró el pedido {numero_pedido}."}
            _registrar_accion("consultar_estado_pedido", {"numero_pedido": numero_pedido}, resultado)
            return json.dumps(resultado, ensure_ascii=False)
        pedido = fila.iloc[0]
        info = {"encontrado": True, "numero_pedido": numero_pedido}
        for col in pedido.index:
            if col != "contenido" and pd.notna(pedido[col]):
                info[str(col).lower().replace(" ", "_")] = str(pedido[col])
        _registrar_accion("consultar_estado_pedido", {"numero_pedido": numero_pedido}, info)
        return json.dumps(info, ensure_ascii=False)

    @tool
    def verificar_elegibilidad_devolucion(pedido_id: str, motivo: str) -> str:
        """Verifica si un pedido es elegible para devolución.
        Requiere número de pedido y motivo de la devolución.
        Args:
            pedido_id: Identificador del pedido, por ejemplo ECO-12345.
            motivo: Razón de la devolución.
        """
        pedido_id = pedido_id.strip().upper()
        motivo = motivo.strip().lower()
        fila = df_pedidos[df_pedidos["pedido_id"].str.upper() == pedido_id]

        if fila.empty:
            resultado = {"pedido_id": pedido_id, "elegible": False, "mensaje": f"No se encontró el pedido {pedido_id}."}
            _registrar_accion("verificar_elegibilidad_devolucion", {"pedido_id": pedido_id, "motivo": motivo}, resultado)
            return json.dumps(resultado, ensure_ascii=False)

        pedido = fila.iloc[0]
        estado = pedido["estado"]
        cliente = pedido["cliente"]
        producto = pedido["producto"]

        ESTADOS_ELEGIBLES = {"ENTREGADO", "LISTO PARA RECOGIDA"}
        if estado not in ESTADOS_ELEGIBLES:
            RAZONES = {
                "EN TRÁNSITO": "aún está EN TRÁNSITO.",
                "RETRASADO": "está RETRASADO y no ha sido entregado.",
                "PROCESANDO": "está siendo PROCESADO.",
                "CANCELADO": "fue CANCELADO.",
                "PENDIENTE DE PAGO": "está PENDIENTE DE PAGO.",
                "RETENIDO EN ADUANA": "está RETENIDO EN ADUANA.",
                "DEVUELTO": "ya fue DEVUELTO previamente.",
            }
            razon = RAZONES.get(estado, f"tiene estado {estado}.")
            resultado = {"pedido_id": pedido_id, "cliente": cliente, "producto": producto, "estado": estado, "elegible": False, "mensaje": f"No elegible porque {razon}"}
            _registrar_accion("verificar_elegibilidad_devolucion", {"pedido_id": pedido_id, "motivo": motivo}, resultado)
            return json.dumps(resultado, ensure_ascii=False)

        # Daño en tránsito
        if any(kw in motivo for kw in ["dañado", "roto", "aplastado", "defectuoso", "golpeado", "daño", "golpe"]):
            devoluciones_aprobadas[pedido_id] = {"producto": producto, "cliente": cliente, "motivo": motivo, "tipo": "defecto_transito"}
            resultado = {"pedido_id": pedido_id, "cliente": cliente, "producto": producto, "elegible": True, "mensaje": "Aprobada por daño en tránsito.", "costo_envio": "Gratuito", "compensacion": "Cupón 10%"}
            _registrar_accion("verificar_elegibilidad_devolucion", {"pedido_id": pedido_id, "motivo": motivo}, resultado)
            return json.dumps(resultado, ensure_ascii=False)

        # Higiene
        producto_lower = producto.lower()
        for cat in PRODUCTOS_HIGIENE:
            if cat in producto_lower:
                resultado = {"pedido_id": pedido_id, "cliente": cliente, "producto": producto, "elegible": False, "mensaje": f"Productos de higiene ({producto}) no elegibles.", "alternativa": "Crédito en tienda vía soporte@ecomarket.com"}
                _registrar_accion("verificar_elegibilidad_devolucion", {"pedido_id": pedido_id, "motivo": motivo}, resultado)
                return json.dumps(resultado, ensure_ascii=False)

        # Perecederos
        for cat in PRODUCTOS_PERECEDEROS:
            if cat in producto_lower:
                resultado = {"pedido_id": pedido_id, "cliente": cliente, "producto": producto, "elegible": False, "mensaje": f"Productos perecederos ({producto}) no elegibles.", "alternativa": "Reembolso especial si llegó en mal estado."}
                _registrar_accion("verificar_elegibilidad_devolucion", {"pedido_id": pedido_id, "motivo": motivo}, resultado)
                return json.dumps(resultado, ensure_ascii=False)

        # Plazo 30 días
        fecha_ref = pedido.get("entrega_real") if pd.notna(pedido.get("entrega_real")) else pedido.get("fecha_pedido")
        if pd.notna(fecha_ref):
            try:
                dias = (datetime.now() - pd.to_datetime(fecha_ref)).days
                if dias > 30:
                    resultado = {"pedido_id": pedido_id, "cliente": cliente, "producto": producto, "elegible": False, "mensaje": f"Plazo de 30 días expirado ({dias} días).", "alternativa": "Contacta soporte para excepciones."}
                    _registrar_accion("verificar_elegibilidad_devolucion", {"pedido_id": pedido_id, "motivo": motivo}, resultado)
                    return json.dumps(resultado, ensure_ascii=False)
            except (ValueError, TypeError):
                pass

        # Aprobada
        devoluciones_aprobadas[pedido_id] = {"producto": producto, "cliente": cliente, "motivo": motivo, "tipo": "devolucion_estandar"}
        resultado = {"pedido_id": pedido_id, "cliente": cliente, "producto": producto, "elegible": True, "mensaje": "Devolución aprobada.", "plazo_reembolso": "5-7 días hábiles", "costo_envio": "3.95€"}
        _registrar_accion("verificar_elegibilidad_devolucion", {"pedido_id": pedido_id, "motivo": motivo}, resultado)
        return json.dumps(resultado, ensure_ascii=False)

    @tool
    def generar_etiqueta_devolucion(pedido_id: str) -> str:
        """Genera etiqueta de devolución para un pedido previamente aprobado.
        SOLO usar después de verificar elegibilidad.
        Args:
            pedido_id: Identificador del pedido elegible.
        """
        pedido_id = pedido_id.strip().upper()
        if pedido_id not in devoluciones_aprobadas:
            resultado = {"pedido_id": pedido_id, "exito": False, "mensaje": "No hay devolución aprobada. Verifica elegibilidad primero."}
            _registrar_accion("generar_etiqueta_devolucion", {"pedido_id": pedido_id}, resultado)
            return json.dumps(resultado, ensure_ascii=False)

        info = devoluciones_aprobadas[pedido_id]
        codigo = f"DEV-{hashlib.md5(f'{pedido_id}{datetime.now().isoformat()}'.encode()).hexdigest()[:8].upper()}"
        fecha_limite = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")

        if info.get("tipo") == "defecto_transito":
            transportista = "DHL Express (recogida a domicilio gratuita)"
            costo = "GRATUITO"
        else:
            transportista = "Correos — Punto de recogida"
            costo = "3.95€"

        resultado = {
            "exito": True, "codigo_devolucion": codigo, "pedido_id": pedido_id,
            "producto": info.get("producto"), "transportista": transportista,
            "costo_envio": costo, "fecha_limite_envio": fecha_limite,
            "direccion": "Centro Devoluciones EcoMarket — C/ Sostenibilidad 42, 28042 Madrid",
        }
        _registrar_accion("generar_etiqueta_devolucion", {"pedido_id": pedido_id}, resultado)
        return json.dumps(resultado, ensure_ascii=False)

    @tool
    def consultar_base_conocimiento(pregunta: str) -> str:
        """Responde preguntas generales sobre política, FAQ y estado de pedidos de EcoMarket.
        Args:
            pregunta: Consulta en lenguaje natural.
        """
        try:
            respuesta = qa_chain.run(pregunta)
            _registrar_accion("consultar_base_conocimiento", {"pregunta": pregunta[:100]}, {"respuesta": respuesta[:200]})
            return respuesta
        except Exception as e:
            return f"Error: {str(e)}"

    tools = [consultar_estado_pedido, verificar_elegibilidad_devolucion, generar_etiqueta_devolucion, consultar_base_conocimiento]

    SYSTEM_PROMPT = """Eres EcoBot, asistente virtual de EcoMarket (productos sostenibles).

ROL: Soporte empático, claro y honesto. Tono cálido pero profesional.

HERRAMIENTAS:
- consultar_estado_pedido: estado/tracking de pedidos (sin devolución)
- verificar_elegibilidad_devolucion: verificar si un pedido puede devolverse (necesita pedido + motivo)
- generar_etiqueta_devolucion: generar etiqueta SOLO después de verificar elegibilidad
- consultar_base_conocimiento: preguntas generales sobre políticas/FAQ

FLUJO DEVOLUCIONES:
1. Pide número de pedido si no lo tiene.
2. Pide motivo si no lo tiene.
3. Llama verificar_elegibilidad_devolucion.
4. Si ELEGIBLE → llama generar_etiqueta_devolucion → presenta instrucciones.
5. Si NO ELEGIBLE → explica con empatía + alternativa.

REGLAS:
- Responde SIEMPRE en español.
- NUNCA inventes datos.
- Contacto: soporte@ecomarket.com / +34 900 123 456
- Cierra con: ¿Hay algo más en lo que pueda ayudarte?"""

    return create_agent(model=llm, tools=tools, system_prompt=SYSTEM_PROMPT)


# ─────────────────────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="main-header"><h1>🌿 EcoBot — Asistente EcoMarket</h1><p>Asistente IA para pedidos, devoluciones y más.</p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## 🛠️ Capacidades")
    st.markdown("- 📦 Estado de pedidos\n- 🔄 Verificar devoluciones\n- 🏷️ Generar etiquetas\n- 📚 Base de conocimiento")
    st.markdown("---")
    st.markdown("## 💡 Ejemplos")
    st.markdown("- *¿Estado de ECO-12345?*\n- *Quiero devolver ECO-12347*\n- *¿Política de devoluciones?*")
    st.markdown("---")
    st.markdown("**Modelo:** LLaMA 3.3 70B (Groq)  \n**Framework:** LangChain  \n**Vector Store:** ChromaDB")

with st.spinner("🔄 Inicializando..."):
    llm, qa_chain, df_pedidos = inicializar_sistema()
    agent = crear_agente(llm, qa_chain, df_pedidos)

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar="🌿" if message["role"] == "assistant" else "👤"):
        st.markdown(message["content"])

if prompt := st.chat_input("Escribe tu consulta aquí..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🌿"):
        with st.spinner("EcoBot está procesando..."):
            try:
                resultado = agent.invoke({"messages": [HumanMessage(content=prompt)]})
                mensajes = resultado["messages"]
                respuesta = ""
                for msg in reversed(mensajes):
                    if hasattr(msg, "content") and len(str(msg.content).strip()) > 30:
                        respuesta = str(msg.content)
                        break
                if not respuesta:
                    respuesta = str(mensajes[-1].content)
            except Exception as e:
                respuesta = f"Lo siento, ocurrió un error. Contacta soporte@ecomarket.com.\n\nDetalle: {str(e)}"

        st.markdown(respuesta)

    st.session_state.messages.append({"role": "assistant", "content": respuesta})

if st.session_state.messages:
    if st.button("🗑️ Limpiar conversación"):
        st.session_state.messages = []
        st.session_state.devoluciones_aprobadas = {}
        st.rerun()
