const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function friendlyHttpError(status) {
  if (status === 422) {
    return "Please check your question. It must be between 1 and 1000 characters.";
  }
  if (status === 503) {
    return "The assistant is busy right now. Please try again in a moment.";
  }
  return "Something went wrong while contacting the server. Please try again.";
}

async function requestJson(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options);
  } catch {
    throw new Error(
      "Unable to connect to the legal assistant server. Please check that the backend is running."
    );
  }

  if (!response.ok) {
    throw new Error(friendlyHttpError(response.status));
  }

  return response.json();
}

export async function askLegalAssistant(
  query,
  sessionId = null,
  responseLang = "auto"
) {
  return requestJson("/api/ask", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      query,
      session_id: sessionId,
      response_lang: responseLang,
    }),
  });
}

export async function getExamples() {
  return requestJson("/api/examples", { method: "GET" });
}

export async function getHealth() {
  return requestJson("/api/health", { method: "GET" });
}

export async function createDraft(body) {
  return requestJson("/api/draft", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
}

export async function deleteSession(id) {
  return requestJson(`/api/session/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}
