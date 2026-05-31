export class ApiError extends Error {
  status: number;
  code: string;

  constructor(message: string, status = 500, code = "API_ERROR") {
    super(message);
    this.status = status;
    this.code = code;
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
const AUTH_SESSION_KEY = "fraudshield2026.session";

function readAccessToken() {
  if (typeof window === "undefined") {
    return "";
  }

  const rawValue = window.localStorage.getItem(AUTH_SESSION_KEY);
  if (!rawValue) {
    return "";
  }

  try {
    const parsed = JSON.parse(rawValue) as { accessToken?: string };
    return parsed.accessToken ?? "";
  } catch {
    return "";
  }
}

function buildHeaders(headers?: HeadersInit) {
  const nextHeaders = new Headers(headers);
  const accessToken = readAccessToken();
  if (accessToken && !nextHeaders.has("Authorization")) {
    nextHeaders.set("Authorization", `Bearer ${accessToken}`);
  }
  return nextHeaders;
}

async function parseResponse<T>(response: Response): Promise<T> {
  const text = await response.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!response.ok) {
    const errorCode =
      typeof data === "object" && data !== null && "error" in data
        ? (data as { error?: { code?: string } }).error?.code ?? "API_ERROR"
        : "API_ERROR";
    const detailMessage =
      typeof data === "object" && data !== null && "detail" in data
        ? Array.isArray((data as { detail?: unknown }).detail)
          ? (data as { detail: Array<{ msg?: string }> }).detail
              .map((item) => item.msg)
              .filter(Boolean)
              .join("；")
          : typeof (data as { detail?: unknown }).detail === "string"
            ? (data as { detail: string }).detail
            : ""
        : "";
    const message =
      (typeof data === "object" && data !== null && "error" in data
        ? (data as { error?: { message?: string } }).error?.message
        : "") ||
      detailMessage ||
      (typeof data === "string" ? data : "") ||
      "服务请求失败";
    throw new ApiError(message, response.status, errorCode);
  }

  return data as T;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: buildHeaders(init?.headers),
    });
  } catch (error) {
    if (error instanceof TypeError) {
      throw new ApiError("无法连接到后端服务，请确认 8000 端口服务已启动", 0, "NETWORK_ERROR");
    }
    throw error;
  }
  return parseResponse<T>(response);
}

async function requestBlob(path: string, init?: RequestInit): Promise<Blob> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: buildHeaders(init?.headers),
    });
  } catch (error) {
    if (error instanceof TypeError) {
      throw new ApiError("无法连接到后端服务，请确认 8000 端口服务已启动", 0, "NETWORK_ERROR");
    }
    throw error;
  }

  if (!response.ok) {
    await parseResponse<null>(response);
  }
  return response.blob();
}

export async function apiGet<T>(path: string): Promise<T> {
  return request<T>(path);
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
}

export async function apiPostForm<T>(path: string, body: FormData): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body,
  });
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
}

export async function apiDelete(path: string): Promise<void> {
  await request<null>(path, {
    method: "DELETE",
  });
}

export async function apiDeleteJson<T>(path: string): Promise<T> {
  return request<T>(path, {
    method: "DELETE",
  });
}

export async function apiGetBlob(path: string): Promise<Blob> {
  return requestBlob(path);
}

export function createEventStream(path: string): EventSource {
  const token = readAccessToken();
  const separator = path.includes("?") ? "&" : "?";
  const url = token
    ? `${API_BASE_URL}${path}${separator}token=${encodeURIComponent(token)}`
    : `${API_BASE_URL}${path}`;
  return new EventSource(url);
}
