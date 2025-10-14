type EagleViewTokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  scope: string;
};

type CachedToken = {
  token: string;
  expiresAt: number;
};

let tokenCache: CachedToken | null = null;

const authUrl = (import.meta.env.VITE_EAGLEVIEW_AUTH_URL || "").trim();
const apiToken = (import.meta.env.VITE_ACORD_API_TOKEN || "").trim();

export const getEagleViewBearerToken = async (): Promise<string | null> => {
  if (!authUrl || !apiToken) {
    console.error("EagleView auth URL or API token not configured");
    return null;
  }

  const now = Date.now();
  if (tokenCache && tokenCache.expiresAt > now) {
    return tokenCache.token;
  }

  try {
    const response = await fetch(`${authUrl}/api/v1/eagleview/token`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${apiToken}`
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch EagleView token: ${response.status}`);
    }

    const data: EagleViewTokenResponse = await response.json();

    const expiresAt = now + (data.expires_in - 60) * 1000;

    tokenCache = {
      token: data.access_token,
      expiresAt
    };

    return data.access_token;
  } catch (error) {
    console.error("Error fetching EagleView bearer token:", error);
    return null;
  }
};

export const clearTokenCache = () => {
  tokenCache = null;
};
