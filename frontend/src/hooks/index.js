import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Hook for polling data at regular intervals
 */
export function usePolling(fetchFn, interval = 5000, enabled = true) {
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(true);
    const intervalRef = useRef(null);

    const fetchData = useCallback(async () => {
        try {
            const result = await fetchFn();
            setData(result);
            setError(null);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [fetchFn]);

    useEffect(() => {
        if (!enabled) return;

        fetchData();
        intervalRef.current = setInterval(fetchData, interval);

        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
            }
        };
    }, [fetchData, interval, enabled]);

    const refetch = useCallback(() => {
        setLoading(true);
        fetchData();
    }, [fetchData]);

    return { data, error, loading, refetch };
}

/**
 * Hook for async operations with loading state
 */
export function useAsync(asyncFn) {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [data, setData] = useState(null);

    const execute = useCallback(async (...args) => {
        setLoading(true);
        setError(null);
        try {
            const result = await asyncFn(...args);
            setData(result);
            return result;
        } catch (err) {
            setError(err.message);
            throw err;
        } finally {
            setLoading(false);
        }
    }, [asyncFn]);

    return { execute, loading, error, data };
}

/**
 * Hook for managing local storage
 */
export function useLocalStorage(key, initialValue) {
    const [storedValue, setStoredValue] = useState(() => {
        try {
            const item = window.localStorage.getItem(key);
            return item ? JSON.parse(item) : initialValue;
        } catch (error) {
            return initialValue;
        }
    });

    const setValue = useCallback((value) => {
        try {
            const valueToStore = value instanceof Function ? value(storedValue) : value;
            setStoredValue(valueToStore);
            window.localStorage.setItem(key, JSON.stringify(valueToStore));
        } catch (error) {
            console.error('Error saving to localStorage:', error);
        }
    }, [key, storedValue]);

    return [storedValue, setValue];
}
