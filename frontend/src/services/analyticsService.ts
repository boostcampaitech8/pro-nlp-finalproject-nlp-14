import api from './api';

interface ActivityEvent {
  event_type: 'page_view' | 'click' | 'scroll' | 'input' | 'form_submit';
  event_target: string | null;
  page_path: string;
  metadata: Record<string, unknown> | null;
  timestamp: string;
}

class AnalyticsService {
  private queue: ActivityEvent[] = [];
  private sessionId: string = '';
  private flushInterval: number | null = null;
  private lastScrollDepth = 0;
  private isInitialized = false;

  init(): void {
    if (this.isInitialized) return;
    this.isInitialized = true;

    this.sessionId = this.getOrCreateSessionId();
    this.attachGlobalListeners();
    this.startFlushInterval();
    this.trackPageView(); // Initial page view
  }

  private getOrCreateSessionId(): string {
    let sessionId = sessionStorage.getItem('analytics_session_id');
    if (!sessionId) {
      sessionId = crypto.randomUUID();
      sessionStorage.setItem('analytics_session_id', sessionId);
    }
    return sessionId;
  }

  private attachGlobalListeners(): void {
    // Page navigation
    window.addEventListener('popstate', () => this.trackPageView());

    // Clicks - capture phase to catch all
    document.addEventListener('click', (e) => this.handleClick(e), true);

    // Scroll - throttled
    let scrollTimeout: number | null = null;
    window.addEventListener('scroll', () => {
      if (scrollTimeout) return;
      scrollTimeout = window.setTimeout(() => {
        this.handleScroll();
        scrollTimeout = null;
      }, 1000);
    });

    // Input blur
    document.addEventListener('blur', (e) => this.handleInputBlur(e), true);

    // Form submit
    document.addEventListener('submit', (e) => this.handleFormSubmit(e), true);

    // Flush on page unload
    window.addEventListener('beforeunload', () => this.flush());

    // Override history methods for SPA navigation
    const originalPushState = history.pushState.bind(history);
    history.pushState = (...args) => {
      originalPushState(...args);
      this.trackPageView();
    };
  }

  private trackPageView(): void {
    this.track({
      event_type: 'page_view',
      event_target: document.title,
      page_path: window.location.pathname,
      metadata: {
        referrer: document.referrer,
        search: window.location.search,
      },
      timestamp: new Date().toISOString(),
    });
  }

  private handleClick(e: MouseEvent): void {
    const target = e.target as HTMLElement;
    if (!target) return;

    // Only track meaningful clicks
    const trackable = target.closest('button, a, [data-track], [role="button"]');
    if (!trackable) return;

    const el = trackable as HTMLElement;
    this.track({
      event_type: 'click',
      event_target: this.getElementIdentifier(el),
      page_path: window.location.pathname,
      metadata: {
        x: e.clientX,
        y: e.clientY,
        tag: el.tagName.toLowerCase(),
      },
      timestamp: new Date().toISOString(),
    });
  }

  private handleScroll(): void {
    const scrollHeight = document.documentElement.scrollHeight - window.innerHeight;
    const depth = scrollHeight > 0 ? Math.round((window.scrollY / scrollHeight) * 100) : 0;
    const direction = depth > this.lastScrollDepth ? 'down' : 'up';

    // Only track significant changes (10% increments)
    if (Math.abs(depth - this.lastScrollDepth) < 10) return;

    this.track({
      event_type: 'scroll',
      event_target: null,
      page_path: window.location.pathname,
      metadata: {
        depth,
        direction,
      },
      timestamp: new Date().toISOString(),
    });
    this.lastScrollDepth = depth;
  }

  private handleInputBlur(e: FocusEvent): void {
    const target = e.target as HTMLInputElement;
    if (!target || !['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return;

    // Privacy: only track field name, not value
    this.track({
      event_type: 'input',
      event_target: target.name || target.id || target.placeholder || 'unnamed',
      page_path: window.location.pathname,
      metadata: {
        type: target.type,
        tag: target.tagName.toLowerCase(),
      },
      timestamp: new Date().toISOString(),
    });
  }

  private handleFormSubmit(e: Event): void {
    const form = e.target as HTMLFormElement;
    if (!form || form.tagName !== 'FORM') return;

    this.track({
      event_type: 'form_submit',
      event_target: form.name || form.id || 'unnamed_form',
      page_path: window.location.pathname,
      metadata: {
        action: form.action,
        method: form.method,
      },
      timestamp: new Date().toISOString(),
    });
  }

  private getElementIdentifier(el: HTMLElement): string {
    const parts: string[] = [];
    if (el.id) parts.push(`#${el.id}`);
    if (el.className && typeof el.className === 'string') {
      parts.push(`.${el.className.split(' ').slice(0, 2).join('.')}`);
    }
    const text = el.textContent?.trim().slice(0, 30);
    if (text) parts.push(`"${text}"`);
    return parts.join(' ') || el.tagName.toLowerCase();
  }

  private track(event: ActivityEvent): void {
    this.queue.push(event);
    if (this.queue.length >= 10) {
      this.flush();
    }
  }

  private startFlushInterval(): void {
    this.flushInterval = window.setInterval(() => this.flush(), 5000);
  }

  private async flush(): Promise<void> {
    if (this.queue.length === 0) return;

    const events = [...this.queue];
    this.queue = [];

    try {
      await api.post('/logs/activity', {
        session_id: this.sessionId,
        events,
      });
    } catch (error) {
      // On error, put events back in queue (up to 100 max)
      this.queue = [...events, ...this.queue].slice(0, 100);
      console.warn('[Analytics] Failed to send events:', error);
    }
  }

  // Manual tracking method for custom events
  trackEvent(eventType: string, target: string, metadata?: Record<string, unknown>): void {
    this.track({
      event_type: eventType as ActivityEvent['event_type'],
      event_target: target,
      page_path: window.location.pathname,
      metadata: metadata || null,
      timestamp: new Date().toISOString(),
    });
  }

  destroy(): void {
    if (this.flushInterval) {
      clearInterval(this.flushInterval);
    }
    this.flush();
  }
}

export const analyticsService = new AnalyticsService();
export default analyticsService;
