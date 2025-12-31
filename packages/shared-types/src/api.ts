// 이 파일은 openapi-typescript에 의해 자동 생성됩니다.
// pnpm run generate:types 명령을 실행하여 갱신하세요.

// 임시 타입 정의 (generate 전까지 사용)
export interface paths {
  '/api/v1/auth/register': {
    post: {
      requestBody: {
        content: {
          'application/json': components['schemas']['RegisterRequest'];
        };
      };
      responses: {
        201: {
          content: {
            'application/json': components['schemas']['AuthResponse'];
          };
        };
      };
    };
  };
  '/api/v1/auth/login': {
    post: {
      requestBody: {
        content: {
          'application/json': components['schemas']['LoginRequest'];
        };
      };
      responses: {
        200: {
          content: {
            'application/json': components['schemas']['AuthResponse'];
          };
        };
      };
    };
  };
  '/api/v1/auth/refresh': {
    post: {
      requestBody: {
        content: {
          'application/json': components['schemas']['RefreshTokenRequest'];
        };
      };
      responses: {
        200: {
          content: {
            'application/json': components['schemas']['TokenResponse'];
          };
        };
      };
    };
  };
  '/api/v1/auth/logout': {
    post: {
      responses: {
        204: {
          content: never;
        };
      };
    };
  };
  '/api/v1/auth/me': {
    get: {
      responses: {
        200: {
          content: {
            'application/json': components['schemas']['User'];
          };
        };
      };
    };
  };
}

export interface components {
  schemas: {
    ErrorResponse: {
      error: string;
      message: string;
      details?: Record<string, unknown>;
    };
    PaginationMeta: {
      page: number;
      limit: number;
      total: number;
      totalPages: number;
    };
    UUID: string;
    Timestamp: string;
    AuthProvider: 'local' | 'google' | 'github';
    User: {
      id: string;
      email: string;
      name: string;
      authProvider: components['schemas']['AuthProvider'];
      createdAt: string;
      updatedAt: string;
    };
    RegisterRequest: {
      email: string;
      password: string;
      name: string;
    };
    LoginRequest: {
      email: string;
      password: string;
    };
    TokenResponse: {
      accessToken: string;
      refreshToken: string;
      tokenType: 'Bearer';
      expiresIn: number;
    };
    AuthResponse: {
      user: components['schemas']['User'];
      tokens: components['schemas']['TokenResponse'];
    };
    RefreshTokenRequest: {
      refreshToken: string;
    };
  };
}

export interface operations {}
