import { useState, useEffect } from 'react';
import type { CurriculumData } from '@/../../shared/types';

export function useCurriculum() {
  const [data, setData] = useState<CurriculumData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/curriculum-data.json')
      .then(res => {
        if (!res.ok) throw new Error('Failed to load curriculum data');
        return res.json();
      })
      .then(data => {
        setData(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return { data, loading, error };
}
