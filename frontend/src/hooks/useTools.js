import { useState, useEffect, useCallback } from 'react';
import { listTools, createTool, updateTool, deleteTool, testTool } from '../api/tools';

/**
 * Hook for managing tools list state: loading, data, CRUD, test.
 */
export default function useTools() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchTools = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listTools();
      setItems(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load tools');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTools();
  }, [fetchTools]);

  const handleCreate = useCallback(
    async (data) => {
      const tool = await createTool(data);
      await fetchTools();
      return tool;
    },
    [fetchTools]
  );

  const handleUpdate = useCallback(
    async (id, data) => {
      const tool = await updateTool(id, data);
      await fetchTools();
      return tool;
    },
    [fetchTools]
  );

  const handleDelete = useCallback(
    async (id) => {
      await deleteTool(id);
      await fetchTools();
    },
    [fetchTools]
  );

  const handleTest = useCallback(async (id, testInput = null) => {
    const result = await testTool(id, testInput);
    return result;
  }, []);

  return {
    items,
    loading,
    error,
    refetch: fetchTools,
    create: handleCreate,
    update: handleUpdate,
    remove: handleDelete,
    test: handleTest,
  };
}
