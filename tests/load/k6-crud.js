// RNF-001: "La API DEBE responder solicitudes CRUD comunes con p95 <= 500ms
// bajo carga de referencia."
//
// Este script mide SOLO la plataforma (auth + datasets + analyses + health),
// nunca el agente de IA: /api/analyses POST (que dispara el agente contra un
// LLM externo real) queda deliberadamente afuera - esa latencia depende de
// un proveedor externo (Moonshot/Kimi) y no es representativa de "nuestra"
// API. Ver tests/load/README.md para el detalle de que mide y por que.
//
// Login vive en setup() (corre UNA sola vez, sin importar cuantos VUs/
// iteraciones haya) porque POST /api/auth/login tiene rate limit de
// 5/minuto por IP (backend/app/core/rate_limit.py, settings.rate_limit_auth).
// Si el login estuviera en el default() function, cada VU intentaria
// loguearse en cada iteracion y el rate limiter tumbaria la carga con 429
// casi de inmediato. El resto de los endpoints cubiertos aca no tiene
// rate limit (o uno mucho mas alto, ver settings.rate_limit_expensive que
// ni siquiera aplica a GETs), asi que reusar el mismo token en todas las
// iteraciones es seguro y representativo de un uso real (SPA con sesion).

import http from "k6/http";
import { check, fail, sleep } from "k6";
import { Trend } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const LOGIN_EMAIL = __ENV.LOAD_TEST_EMAIL || "fase2test@example.com";
const LOGIN_PASSWORD = __ENV.LOAD_TEST_PASSWORD || "correcthorsebattery";

// "Carga de referencia" para RNF-001, definida explicitamente aca (el SRS no
// fija un numero para este RNF puntual, a diferencia del RNF-004 de 20
// analisis de agente simultaneos): 20 usuarios virtuales concurrentes
// sostenidos durante 60s, con rampas cortas de 10s arriba/abajo para no
// medir un escalon artificial. Es un perfil de smoke/carga moderada para una
// API CRUD, no una prueba de stress ni de limite de capacidad.
export const options = {
  scenarios: {
    crud_reference_load: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "10s", target: 20 }, // ramp-up
        { duration: "60s", target: 20 }, // carga sostenida = "carga de referencia"
        { duration: "10s", target: 0 }, // ramp-down
      ],
      gracefulRampDown: "5s",
    },
  },
  thresholds: {
    // Umbral global (documental) - el veredicto real por endpoint se lee de
    // los Trends nombrados de abajo, reportados en last_run_results.md.
    http_req_duration: ["p(95)<500"],
    "endpoint_duration{endpoint:health_ready}": ["p(95)<500"],
    "endpoint_duration{endpoint:datasets_list}": ["p(95)<500"],
    "endpoint_duration{endpoint:dataset_schema}": ["p(95)<500"],
    "endpoint_duration{endpoint:analyses_list}": ["p(95)<500"],
    http_req_failed: ["rate<0.01"],
  },
};

// Trend por endpoint para poder leer p50/p95 individuales del summary de k6
// (http_req_duration por si solo mezcla los 4 endpoints + login en un unico
// numero, que no sirve para juzgar el RNF endpoint por endpoint).
const endpointDuration = new Trend("endpoint_duration", true);

export function setup() {
  const loginRes = http.post(
    `${BASE_URL}/api/auth/login`,
    JSON.stringify({ email: LOGIN_EMAIL, password: LOGIN_PASSWORD }),
    { headers: { "Content-Type": "application/json" }, tags: { endpoint: "auth_login" } }
  );

  if (loginRes.status !== 200) {
    fail(
      `Setup: login fallo (status ${loginRes.status}, body ${loginRes.body}). ` +
        `Verificar que la cuenta de carga exista y las credenciales sean correctas.`
    );
  }

  const body = loginRes.json();
  const token = body.access_token;
  const organizationId = body.user.memberships[0].organization_id;

  const authHeaders = { headers: { Authorization: `Bearer ${token}` } };

  // Dataset representativo: se toma el primero que devuelva la organizacion
  // de la cuenta de carga, en vez de hardcodear un UUID que podria dejar de
  // existir si se recrean los datos de prueba.
  const datasetsRes = http.get(
    `${BASE_URL}/api/datasets?organization_id=${organizationId}`,
    authHeaders
  );
  if (datasetsRes.status !== 200) {
    fail(
      `Setup: GET /api/datasets fallo (status ${datasetsRes.status}). ` +
        `La cuenta de carga necesita al menos un dataset importado.`
    );
  }
  const datasets = datasetsRes.json();
  if (!datasets.length) {
    fail("Setup: la organizacion de la cuenta de carga no tiene datasets - importar al menos uno.");
  }

  return {
    token,
    organizationId,
    datasetId: datasets[0].id,
  };
}

export default function (data) {
  const authHeaders = { headers: { Authorization: `Bearer ${data.token}` } };

  const reqs = {
    health_ready: () => http.get(`${BASE_URL}/health/ready`, { tags: { endpoint: "health_ready" } }),
    datasets_list: () =>
      http.get(`${BASE_URL}/api/datasets?organization_id=${data.organizationId}`, {
        ...authHeaders,
        tags: { endpoint: "datasets_list" },
      }),
    dataset_schema: () =>
      http.get(`${BASE_URL}/api/datasets/${data.datasetId}/schema`, {
        ...authHeaders,
        tags: { endpoint: "dataset_schema" },
      }),
    analyses_list: () =>
      http.get(`${BASE_URL}/api/analyses?organization_id=${data.organizationId}`, {
        ...authHeaders,
        tags: { endpoint: "analyses_list" },
      }),
  };

  for (const [name, doRequest] of Object.entries(reqs)) {
    const res = doRequest();
    endpointDuration.add(res.timings.duration, { endpoint: name });
    check(res, {
      [`${name}: status 200`]: (r) => r.status === 200,
    });
  }

  sleep(1); // think time, evita que cada VU martille sin pausa
}
