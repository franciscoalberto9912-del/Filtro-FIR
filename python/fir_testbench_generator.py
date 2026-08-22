#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Herramienta completa para diseño y prueba de filtros FIR en SystemVerilog.

- Calcula y muestra coeficientes para filtros pasa bajos (LPF), pasa altos (HPF)
  y pasa banda (BPF) con ventana de Hamming (u otras).
- Genera señales de prueba (barrido en frecuencia o suma de armónicos) con
  offset y cuantificación de 8 bits (0-255).
- Guarda la señal en formato binario (entrada.txt) para simulación.
- Lee la salida del filtro (salida.txt) y grafica ambas señales para comparar.

Uso: python3 fir_tool.py
"""

import numpy as np
import matplotlib.pyplot as plt
import os

# =============================================================================
#  CONFIGURACIÓN DEL USUARIO (MODIFICA AQUÍ)
# =============================================================================

# --- Parámetros de simulación ---
FS = 13200.0           # Frecuencia de muestreo (Hz)
DURACION = 1         # Duración de la señal (segundos)
OFFSET = 128            # Offset para ADC de 8 bits (centro del rango)

# --- Parámetros del filtro FIR ---
N_COEF = 8              # Número de coeficientes (taps)
VENTANA = 'hamming'     # 'hamming', 'hanning', 'blackman', 'rectangular'

# Frecuencias de corte (Hz) - todas deben ser < FS/2 = 6600 Hz
FC_LP = 1000.0          # Corte para LPF
FC_HP = 2000.0          # Corte para HPF (independiente)
FC_LOW = 500.0         # Corte inferior para BPF
FC_HIGH = 3500.0        # Corte superior para BPF

# --- Parámetros de la señal de prueba ---
MODO_BARRIDO = True     # True: barrido 100 Hz - 6 kHz; False: armónicos
AMPLITUD_BARRIDO = 100  # Amplitud del barrido (si MODO_BARRIDO=True)
AMPLITUD_GLOBAL = 1.0   # Escala global (multiplica todas las amplitudes)

# Solo si MODO_BARRIDO = False:
COMPONENTES = [         # Lista de (frecuencia_Hz, amplitud)
    (5000, 100),
    (10000, 40),
    (15000, 25),
]
RUIDO_AMPLITUD = 0.0    # Amplitud del ruido blanco (0 = sin ruido)

# --- Nombres de archivos ---
ARCHIVO_ENTRADA = "entrada.txt"
ARCHIVO_SALIDA = "salida.txt"
GUARDAR_COEFICIENTES = True  # Guardar coeficientes en archivos .txt

# =============================================================================
#  FUNCIONES DE CÁLCULO DE COEFICIENTES
# =============================================================================

def ventana_aplicar(n, M, tipo='hamming'):
    """
    Devuelve el valor de la ventana para el índice n.
    Tipos soportados: 'hamming', 'hanning', 'blackman', 'rectangular'.
    """
    if M <= 1:
        return 1.0
    if tipo.lower() == 'hamming':
        return 0.54 - 0.46 * np.cos(2 * np.pi * n / (M - 1))
    elif tipo.lower() == 'hanning':
        return 0.5 - 0.5 * np.cos(2 * np.pi * n / (M - 1))
    elif tipo.lower() == 'blackman':
        return 0.42 - 0.5 * np.cos(2 * np.pi * n / (M - 1)) + 0.08 * np.cos(4 * np.pi * n / (M - 1))
    else:  # rectangular
        return 1.0

def sinc(x):
    """Función sinc normalizada: sinc(x) = sin(pi*x)/(pi*x), con sinc(0)=1."""
    if abs(x) < 1e-12:
        return 1.0
    return np.sin(np.pi * x) / (np.pi * x)

def calcular_coeficientes_fir_lp(M, fc, fs, ventana='hamming'):
    """
    Calcula los coeficientes de un filtro pasa bajos (LPF) mediante el método
    de ventana. La frecuencia de corte fc debe ser menor que fs/2.
    Los coeficientes se normalizan para que la ganancia en DC sea 1.
    """
    if fc >= fs/2:
        raise ValueError(f"La frecuencia de corte ({fc} Hz) debe ser menor que fs/2 ({fs/2} Hz).")
    fc_norm = fc / fs   # Frecuencia normalizada (0 a 0.5)
    n = np.arange(M)
    centro = (M - 1) / 2.0
    h = np.zeros(M)
    for i in range(M):
        x = 2 * fc_norm * (i - centro)
        h[i] = 2 * fc_norm * sinc(x)
        h[i] *= ventana_aplicar(i, M, ventana)
    # Normalizar para ganancia DC = 1
    h = h / np.sum(h)
    return h

def calcular_coeficientes_fir_hp(M, fc, fs, ventana='hamming'):
    """
    Calcula coeficientes de un pasa altos (HPF) mediante la transformación
    espectral: h_hp[n] = (-1)^n * h_lp(fs/2 - fc)[n].
    Esto produce un HPF con frecuencia de corte fc, independiente de FC_LP.
    """
    fc_complementaria = fs/2 - fc
    h_lp = calcular_coeficientes_fir_lp(M, fc_complementaria, fs, ventana)
    n = np.arange(M)
    h_hp = h_lp * (-1)**n
    return h_hp

def calcular_coeficientes_fir_bp(M, fc_low, fc_high, fs, ventana='hamming'):
    """
    Calcula coeficientes de un pasa banda (BPF) como resta de dos LPF:
    h_bp = h_lp(fc_high) - h_lp(fc_low).
    Asegura que fc_low < fc_high < fs/2.
    """
    if fc_low >= fc_high:
        raise ValueError("La frecuencia de corte inferior debe ser menor que la superior.")
    if fc_high >= fs/2:
        raise ValueError(f"La frecuencia de corte superior ({fc_high} Hz) debe ser menor que fs/2 ({fs/2} Hz).")
    h_lp_high = calcular_coeficientes_fir_lp(M, fc_high, fs, ventana)
    h_lp_low  = calcular_coeficientes_fir_lp(M, fc_low, fs, ventana)
    h_bp = h_lp_high - h_lp_low
    return h_bp

def coeficientes_a_q214(coefs):
    """
    Convierte coeficientes flotantes a enteros en formato Q2.14
    (escala = 2^14 = 16384) con saturación a 16 bits con signo.
    """
    escala = 2**14
    q = np.round(coefs * escala).astype(int)
    q = np.clip(q, -32768, 32767)
    return q

def imprimir_coeficientes_sv(coefs_q, tipo='LPF'):
    """Imprime los coeficientes en el formato SystemVerilog solicitado."""
    print(f"\n// Coeficientes FIR {tipo} en formato Q2.14 (escala 16384):")
    for i, val in enumerate(coefs_q):
        print(f"        cargar_coeficiente(3'd{i}, 16'sd{val});")
    print()

def guardar_coeficientes_archivo(nombre_archivo, coefs_q, tipo='LPF'):
    """Guarda los coeficientes en un archivo de texto en formato SystemVerilog."""
    with open(nombre_archivo, 'w') as f:
        f.write(f"// Coeficientes FIR {tipo} en formato Q2.14 (escala 16384)\n")
        for i, val in enumerate(coefs_q):
            f.write(f"cargar_coeficiente(3'd{i}, 16'sd{val});\n")

# =============================================================================
#  FUNCIONES DE GENERACIÓN DE SEÑAL
# =============================================================================

def generar_senal_barrido(fs, duracion, f_inicio, f_fin, amp, offset, ruido_amp):
    """
    Genera una señal de barrido lineal en frecuencia (chirp) desde f_inicio
    hasta f_fin, con offset y ruido opcional. Retorna (t, senal_entera).
    """
    N = int(fs * duracion)
    t = np.linspace(0, duracion, N, endpoint=False)
    f_inst = f_inicio + (f_fin - f_inicio) * t / duracion
    fase = 2 * np.pi * np.cumsum(f_inst) / fs
    senal = amp * np.sin(fase)
    if ruido_amp > 0:
        senal += np.random.uniform(-ruido_amp, ruido_amp, N)
    senal = senal + offset
    # Detectar saturación
    if np.any(senal < 0) or np.any(senal > 255):
        print("⚠️  Advertencia: la señal se satura (valores fuera de 0-255). Reduce la amplitud.")
    senal = np.clip(senal, 0, 255)
    senal = np.round(senal).astype(int)
    return t, senal

def generar_senal_armonica(componentes, fs, duracion, offset, ruido_amp, escala=1.0):
    """
    Genera una señal compuesta por la suma de senoides (armónicos) con offset
    y ruido. Cada componente es (frecuencia, amplitud).
    """
    N = int(fs * duracion)
    t = np.linspace(0, duracion, N, endpoint=False)
    senal = np.zeros(N)
    for freq, amp in componentes:
        senal += amp * np.sin(2 * np.pi * freq * t)
    senal *= escala
    if ruido_amp > 0:
        senal += np.random.uniform(-ruido_amp, ruido_amp, N)
    senal = senal + offset
    if np.any(senal < 0) or np.any(senal > 255):
        print("⚠️  Advertencia: la señal se satura. Reduce la amplitud.")
    senal = np.clip(senal, 0, 255)
    senal = np.round(senal).astype(int)
    return t, senal

def guardar_binario(archivo, senal):
    """Guarda un array de enteros (0-255) en formato binario de 8 bits."""
    with open(archivo, 'w') as f:
        for valor in senal:
            f.write(format(valor, '08b') + '\n')
    print(f"✅ Archivo '{archivo}' generado con {len(senal)} muestras.")

def leer_salida_binaria(archivo):
    """Lee un archivo de binarios de 8 bits y devuelve un array de enteros."""
    valores = []
    with open(archivo, 'r') as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                try:
                    valores.append(int(linea, 2))
                except ValueError:
                    print(f"⚠️  Línea ignorada (no es binario): {linea}")
    return np.array(valores)

# =============================================================================
#  FUNCIONES DE VISUALIZACIÓN
# =============================================================================

def graficar_entrada_salida(t_ent, senal_ent, senal_sal, fs, titulo="Comparación"):
    """
    Grafica la señal de entrada y la de salida en dos subplots con el mismo eje X.
    """
    N_sal = len(senal_sal)
    if N_sal > 0:
        t_sal = np.linspace(0, N_sal / fs, N_sal, endpoint=False)
    else:
        t_sal = np.array([])

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    # Entrada
    ax1.step(t_ent, senal_ent, where='mid', color='blue', alpha=0.7, linewidth=1.5)
    ax1.set_ylabel('Valor ADC (0-255)')
    ax1.set_title('Señal de entrada' + (' (barrido)' if MODO_BARRIDO else ' (armónicos)'))
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(-5, 260)

    # Salida
    if N_sal > 0:
        ax2.step(t_sal, senal_sal, where='mid', color='red', alpha=0.7, linewidth=1.5)
        ax2.set_ylabel('Valor filtrado (0-255)')
        ax2.set_title('Señal de salida del FIR')
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(-5, 260)
        ax2.set_xlabel('Tiempo (s)')
    else:
        ax2.text(0.5, 0.5, 'Archivo de salida no encontrado', ha='center', va='center', transform=ax2.transAxes)
        ax2.set_title('Salida no disponible')

    plt.tight_layout()
    plt.show()

# =============================================================================
#  MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("     HERRAMIENTA PARA FILTROS FIR Y SEÑALES DE PRUEBA")
    print("=" * 60)

    # ----- 1. Cálculo y presentación de coeficientes -----
    print("\n📊 Calculando coeficientes para LPF, HPF y BPF...")
    print(f"   Frecuencia de muestreo: {FS/1000:.1f} kHz")
    print(f"   Número de coeficientes: {N_COEF}")
    print(f"   Ventana: {VENTANA}")
    print(f"   LPF: fc = {FC_LP:.1f} Hz")
    print(f"   HPF: fc = {FC_HP:.1f} Hz")
    print(f"   BPF: fc_low = {FC_LOW:.1f} Hz, fc_high = {FC_HIGH:.1f} Hz")
    print()

    try:
        # LPF
        coefs_lp = calcular_coeficientes_fir_lp(N_COEF, FC_LP, FS, VENTANA)
        coefs_q_lp = coeficientes_a_q214(coefs_lp)
        imprimir_coeficientes_sv(coefs_q_lp, 'LPF')
        if GUARDAR_COEFICIENTES:
            guardar_coeficientes_archivo("coef_LPF.txt", coefs_q_lp, 'LPF')

        # HPF (ahora con su propia frecuencia de corte, gracias a la corrección)
        coefs_hp = calcular_coeficientes_fir_hp(N_COEF, FC_HP, FS, VENTANA)
        coefs_q_hp = coeficientes_a_q214(coefs_hp)
        imprimir_coeficientes_sv(coefs_q_hp, 'HPF')
        if GUARDAR_COEFICIENTES:
            guardar_coeficientes_archivo("coef_HPF.txt", coefs_q_hp, 'HPF')

        # BPF
        coefs_bp = calcular_coeficientes_fir_bp(N_COEF, FC_LOW, FC_HIGH, FS, VENTANA)
        coefs_q_bp = coeficientes_a_q214(coefs_bp)
        imprimir_coeficientes_sv(coefs_q_bp, 'BPF')
        if GUARDAR_COEFICIENTES:
            guardar_coeficientes_archivo("coef_BPF.txt", coefs_q_bp, 'BPF')

        print("✅ Coeficientes calculados. Los archivos 'coef_*.txt' han sido guardados.\n")

    except ValueError as e:
        print(f"❌ Error en el cálculo de coeficientes: {e}")
        return

    # ----- 2. Generación de la señal de entrada (barrido 100 Hz → 6 kHz) -----
    print("🔊 Generando señal de prueba...")
    if MODO_BARRIDO:
        print(f"   Modo barrido: 100 Hz → 6 kHz, amplitud = {AMPLITUD_BARRIDO * AMPLITUD_GLOBAL:.1f}")
        t, senal_entrada = generar_senal_barrido(
            FS, DURACION, 100.0, 6000.0,   # <--- Barrido corregido
            AMPLITUD_BARRIDO * AMPLITUD_GLOBAL,
            OFFSET, RUIDO_AMPLITUD
        )
    else:
        print("   Modo armónico:")
        for f, a in COMPONENTES:
            print(f"     {f/1000:.1f} kHz, amplitud {a:.1f}")
        t, senal_entrada = generar_senal_armonica(
            COMPONENTES, FS, DURACION, OFFSET, RUIDO_AMPLITUD, AMPLITUD_GLOBAL
        )

    guardar_binario(ARCHIVO_ENTRADA, senal_entrada)

    # ----- 3. Lectura de la salida (si existe) -----
    if os.path.exists(ARCHIVO_SALIDA):
        print(f"📂 Leyendo '{ARCHIVO_SALIDA}'...")
        senal_salida = leer_salida_binaria(ARCHIVO_SALIDA)
        print(f"   Se leyeron {len(senal_salida)} muestras.")
    else:
        print(f"⚠️  Archivo '{ARCHIVO_SALIDA}' no encontrado. Solo se graficará la entrada.")
        senal_salida = np.array([])

    # ----- 4. Graficar -----
    print("\n📈 Generando gráficas...")
    graficar_entrada_salida(t, senal_entrada, senal_salida, FS)

    print("\n🎯 ¡Proceso completado!")

if __name__ == "__main__":
    main()
