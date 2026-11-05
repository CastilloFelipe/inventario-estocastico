"""Diagnóstico y muestreo de la demanda diaria (independiente del simulador)."""
import numpy as np
from scipy import stats

# Cortes de Syntetos-Boylan
ADI_CORTE = 1.32
CV2_CORTE = 0.49


def primera_venta(ventas: np.ndarray) -> np.ndarray:
    """Índice del primer día con venta por producto (-1 si nunca vende)."""
    hay = np.asarray(ventas) > 0
    return np.where(hay.any(axis=0), hay.argmax(axis=0), -1).astype(np.int64)


def clasificar(ventas: np.ndarray, inicio: np.ndarray) -> np.ndarray:
    """Clasificación Syntetos-Boylan por producto, usando la historia desde `inicio`."""
    ventas = np.asarray(ventas, dtype=float)
    etiquetas = []
    for j in range(ventas.shape[1]):
        if inicio[j] < 0:
            etiquetas.append("sin_ventas")
            continue
        x = ventas[inicio[j]:, j]
        q = x[x > 0]
        adi = len(x) / len(q)
        cv2 = (q.std() / q.mean()) ** 2
        if adi < ADI_CORTE:
            etiquetas.append("suave" if cv2 < CV2_CORTE else "erratica")
        else:
            etiquetas.append("intermitente" if cv2 < CV2_CORTE else "irregular")
    return np.array(etiquetas, dtype=object)


def ajustar_distribuciones(x: np.ndarray) -> dict:
    """Ajusta normal, Poisson y binomial negativa y elige la de menor AIC."""
    x = np.asarray(x, dtype=float)
    if not (x > 0).any():
        return {"mejor": "sin_ventas", "aic": {}}
    media, var = x.mean(), x.var()
    aic = {}
    if var > 0:
        aic["normal"] = 4 - 2 * stats.norm.logpdf(x, media, np.sqrt(var)).sum()
    aic["poisson"] = 2 - 2 * stats.poisson.logpmf(x, media).sum()
    if var > media:
        n = media**2 / (var - media)
        p = media / var
        aic["binomial_negativa"] = 4 - 2 * stats.nbinom.logpmf(x, n, p).sum()
    aic = {k: float(v) for k, v in aic.items()}
    return {"mejor": min(aic, key=aic.get), "aic": aic}


def censura_sospechosa(x: np.ndarray) -> bool:
    """True si la racha de ceros más larga es improbable bajo ceros independientes."""
    x = np.asarray(x)
    cero = x == 0
    p0 = cero.mean()
    if p0 >= 0.5:
        return False
    lmax = racha = 0
    for c in cero:
        racha = racha + 1 if c else 0
        lmax = max(lmax, racha)
    return bool(len(x) * p0**lmax < 0.01)


def muestrear_demanda(
    rng: np.random.Generator,
    historia: np.ndarray,
    dow_hist: np.ndarray,
    dow_sim: np.ndarray,
    reps: int,
    inicio: np.ndarray,
) -> np.ndarray:
    """Bootstrap por día de semana: (reps, len(dow_sim), items), int64.

    Cada día simulado toma al azar un día histórico del mismo día de semana
    y con índice >= inicio del producto. Si el producto no tiene ninguno,
    usa cualquier día válido; si nunca vende, devuelve ceros.
    """
    historia = np.asarray(historia)
    dow_hist = np.asarray(dow_hist)
    dow_sim = np.asarray(dow_sim)
    dias_h, items = historia.shape
    out = np.zeros((reps, len(dow_sim), items), dtype=np.int64)
    dias_por_dow = {w: np.flatnonzero(dow_hist == w) for w in np.unique(dow_sim)}
    for j in range(items):
        if inicio[j] < 0:
            continue
        validos_todos = np.arange(inicio[j], dias_h)
        for w, dias_w in dias_por_dow.items():
            validos = dias_w[dias_w >= inicio[j]]
            if len(validos) == 0:
                validos = validos_todos
            cols = np.flatnonzero(dow_sim == w)
            u = rng.random((reps, len(cols)))
            idx = validos[(u * len(validos)).astype(np.int64)]
            out[:, cols, j] = np.rint(historia[idx, j]).astype(np.int64)
    return out


def muestrear_demanda_bloques(
    rng: np.random.Generator,
    historia: np.ndarray,
    dow_hist: np.ndarray,
    dow_inicio: int,
    n_dias: int,
    reps: int,
    inicio: np.ndarray,
    bloque: int = 28,
) -> np.ndarray:
    """Bootstrap por bloques: (reps, n_dias, items), int64.

    Cada réplica concatena bloques de `bloque` días consecutivos de la historia
    real del producto (desde su `inicio`), así conserva la dependencia entre
    días. Cada bloque empieza en un día histórico con el mismo día de semana
    que el día simulado donde empieza (el día simulado 0 tiene `dow_inicio`);
    el último bloque se recorta a `n_dias`. Si la historia válida es más corta
    que `bloque`, usa el bloque más largo posible; si ningún inicio válido
    tiene el día de semana pedido, usa cualquiera. Si nunca vende, ceros.
    """
    historia = np.asarray(historia)
    dow_hist = np.asarray(dow_hist)
    dias_h, items = historia.shape
    out = np.zeros((reps, n_dias, items), dtype=np.int64)
    if n_dias <= 0:
        return out
    for j in range(items):
        if inicio[j] < 0:
            continue
        b = max(1, min(int(bloque), dias_h - int(inicio[j])))
        comienzos_todos = np.arange(inicio[j], dias_h - b + 1)
        n_bloques = -(-n_dias // b)
        dow_bloques = (dow_inicio + np.arange(n_bloques) * b) % 7
        comienzos = np.empty((reps, n_bloques), dtype=np.int64)
        for w in np.unique(dow_bloques):
            validos = comienzos_todos[dow_hist[comienzos_todos] == w]
            if len(validos) == 0:
                validos = comienzos_todos
            cols = np.flatnonzero(dow_bloques == w)
            u = rng.random((reps, len(cols)))
            comienzos[:, cols] = validos[(u * len(validos)).astype(np.int64)]
        idx = (comienzos[:, :, None] + np.arange(b)).reshape(reps, -1)[:, :n_dias]
        out[:, :, j] = np.rint(historia[idx, j]).astype(np.int64)
    return out
