/**
 * Custom hook to handle ResizeObserver loop issues
 * Provides a stable ResizeObserver that won't cause infinite loops
 */

import { useEffect, useRef, useCallback } from 'react';

const useResizeObserverFix = () => {
  const observerRef = useRef(null);
  const callbackRef = useRef(null);
  const timeoutRef = useRef(null);
  const isScheduledRef = useRef(false);

  const createStableObserver = useCallback((callback) => {
    if (observerRef.current) {
      observerRef.current.disconnect();
    }

    callbackRef.current = callback;

    const debouncedCallback = (entries, observer) => {
      if (isScheduledRef.current) return;
      
      isScheduledRef.current = true;
      
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      
      timeoutRef.current = setTimeout(() => {
        requestAnimationFrame(() => {
          try {
            if (callbackRef.current && entries.length > 0) {
              callbackRef.current(entries, observer);
            }
          } catch (error) {
            if (!error.message?.includes('ResizeObserver loop')) {
              console.error('ResizeObserver callback error:', error);
            }
          } finally {
            isScheduledRef.current = false;
            timeoutRef.current = null;
          }
        });
      }, 16);
    };

    observerRef.current = new ResizeObserver(debouncedCallback);
    return observerRef.current;
  }, []);

  const observe = useCallback((element, callback) => {
    if (!element) return;
    
    const observer = createStableObserver(callback);
    observer.observe(element);
    
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      observer.unobserve(element);
    };
  }, [createStableObserver]);

  useEffect(() => {
    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return { observe };
};

export default useResizeObserverFix;