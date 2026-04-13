import { useState, useEffect, useCallback } from 'react';
import {
  listWorkflows,
  createWorkflow,
  duplicateWorkflow,
  deleteWorkflow,
} from '../api/workflows';

/**
 * Hook for managing workflows list state: loading, data, pagination, search.
 */
export default function useWorkflows() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage] = useState(20);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchWorkflows = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listWorkflows({ page, perPage, search });
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load workflows');
    } finally {
      setLoading(false);
    }
  }, [page, perPage, search]);

  useEffect(() => {
    fetchWorkflows();
  }, [fetchWorkflows]);

  const handleCreate = useCallback(
    async (data) => {
      const workflow = await createWorkflow(data);
      await fetchWorkflows();
      return workflow;
    },
    [fetchWorkflows]
  );

  const handleDuplicate = useCallback(
    async (id) => {
      const workflow = await duplicateWorkflow(id);
      await fetchWorkflows();
      return workflow;
    },
    [fetchWorkflows]
  );

  const handleDelete = useCallback(
    async (id) => {
      await deleteWorkflow(id);
      await fetchWorkflows();
    },
    [fetchWorkflows]
  );

  return {
    items,
    total,
    page,
    perPage,
    search,
    loading,
    error,
    setPage,
    setSearch,
    refetch: fetchWorkflows,
    create: handleCreate,
    duplicate: handleDuplicate,
    remove: handleDelete,
  };
}
