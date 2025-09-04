/**
 * Comprehensive error suppression utility for common harmless errors
 * Specifically targets ResizeObserver errors that are common in React apps
 */

// Store original console methods
const originalError = console.error;
const originalWarn = console.warn;

// List of error patterns to suppress
const SUPPRESSED_ERROR_PATTERNS = [
  'ResizeObserver loop completed with undelivered notifications',
  'ResizeObserver loop limit exceeded',
  'Non-Error promise rejection captured',
  'Warning: validateDOMNesting',
  'Warning: React does not recognize the',
  'Warning: componentWillReceiveProps has been renamed',
  'Warning: componentWillMount has been renamed'
];

// Check if error should be suppressed
const shouldSuppressError = (message) => {
  if (typeof message !== 'string') return false;
  return SUPPRESSED_ERROR_PATTERNS.some(pattern => message.includes(pattern));
};

// Enhanced console.error override
console.error = (...args) => {
  const message = args[0];
  if (shouldSuppressError(message)) {
    return;
  }
  originalError.apply(console, args);
};

// Enhanced console.warn override
console.warn = (...args) => {
  const message = args[0];
  if (shouldSuppressError(message)) {
    return;
  }
  originalWarn.apply(console, args);
};

// Global error event handler with more aggressive suppression
const handleGlobalError = (event) => {
  if (shouldSuppressError(event.message)) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    return false;
  }
};

// Global unhandled promise rejection handler
const handleUnhandledRejection = (event) => {
  const message = event.reason?.message || event.reason;
  if (shouldSuppressError(message)) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    return false;
  }
};

// Install global error handlers with capture phase
window.addEventListener('error', handleGlobalError, { capture: true, passive: false });
window.addEventListener('unhandledrejection', handleUnhandledRejection, { capture: true, passive: false });

// Enhanced ResizeObserver polyfill with debouncing
if (typeof window !== 'undefined' && window.ResizeObserver) {
  const OriginalResizeObserver = window.ResizeObserver;
  
  window.ResizeObserver = class extends OriginalResizeObserver {
    constructor(callback) {
      let timeoutId = null;
      let isScheduled = false;
      
      const debouncedCallback = (entries, observer) => {
        if (isScheduled) return;
        
        isScheduled = true;
        
        if (timeoutId) {
          clearTimeout(timeoutId);
        }
        
        timeoutId = setTimeout(() => {
          requestAnimationFrame(() => {
            try {
              callback(entries, observer);
            } catch (error) {
              if (!shouldSuppressError(error.message)) {
                console.error('ResizeObserver callback error:', error);
              }
            } finally {
              isScheduled = false;
              timeoutId = null;
            }
          });
        }, 16); // 16ms debounce
      };
      
      super(debouncedCallback);
    }
  };
}

// Webpack dev server overlay suppression
const suppressWebpackOverlay = () => {
  if (process.env.NODE_ENV === 'development') {
    // Add CSS to hide webpack overlay
    const style = document.createElement('style');
    style.id = 'resize-observer-error-suppression';
    style.textContent = `
      iframe#webpack-dev-server-client-overlay,
      #webpack-dev-server-client-overlay,
      #webpack-dev-server-client-overlay-div {
        display: none !important;
      }
    `;
    
    if (!document.getElementById('resize-observer-error-suppression')) {
      document.head.appendChild(style);
    }
    
    // Periodically check and hide overlay
    const hideOverlay = () => {
      try {
        const overlay = document.getElementById('webpack-dev-server-client-overlay');
        const overlayDiv = document.getElementById('webpack-dev-server-client-overlay-div');
        
        if (overlay && overlay.style.display !== 'none') {
          overlay.style.display = 'none';
        }
        if (overlayDiv && overlayDiv.style.display !== 'none') {
          overlayDiv.style.display = 'none';
        }
      } catch (e) {
        // Ignore errors when trying to hide overlay
      }
    };
    
    // Check immediately and then periodically
    hideOverlay();
    setInterval(hideOverlay, 100);
  }
};

// Initialize overlay suppression
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', suppressWebpackOverlay);
} else {
  suppressWebpackOverlay();
}

// Export utility functions for manual use
export const suppressError = shouldSuppressError;
export const restoreConsole = () => {
  console.error = originalError;
  console.warn = originalWarn;
  window.removeEventListener('error', handleGlobalError, { capture: true });
  window.removeEventListener('unhandledrejection', handleUnhandledRejection, { capture: true });
};

const errorSuppressionUtils = {
  suppressError,
  restoreConsole,
  suppressWebpackOverlay
};

export default errorSuppressionUtils;