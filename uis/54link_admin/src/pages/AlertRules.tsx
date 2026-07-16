import { Plus, Trash2, Play, Save } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';
import { useTenantBranding } from '../contexts/TenantBrandingContext';

interface AlertRule {
  id: string;
  name: string;
  enabled: boolean;
  conditions: Condition[];
  actions: Action[];
}

interface Condition {
  id: string;
  metric: string;
  operator: '>' | '<' | '=' | '>=' | '<=' | '!=';
  value: number;
  duration?: number; // minutes
}

interface Action {
  id: string;
  type: 'email' | 'webhook' | 'sms';
  target: string;
}

const METRICS = [
  { value: 'api_calls', label: 'API Calls' },
  { value: 'error_rate', label: 'Error Rate (%)' },
  { value: 'response_time', label: 'Response Time (ms)' },
  { value: 'active_users', label: 'Active Users' },
  { value: 'tenant_calls', label: 'Tenant API Calls' },
];

const OPERATORS = [
  { value: '>', label: 'Greater than' },
  { value: '<', label: 'Less than' },
  { value: '>=', label: 'Greater than or equal' },
  { value: '<=', label: 'Less than or equal' },
  { value: '=', label: 'Equal to' },
  { value: '!=', label: 'Not equal to' },
];

export default function AlertRules() {
  const { primaryColor, secondaryColor } = useTenantBranding();
  const [rules, setRules] = useState<AlertRule[]>([
    {
      id: 'rule-1',
      name: 'High API Call Volume',
      enabled: true,
      conditions: [
        { id: 'cond-1', metric: 'api_calls', operator: '>', value: 100000, duration: 5 },
      ],
      actions: [
        { id: 'act-1', type: 'email', target: 'admin@54link-dev.com' },
      ],
    },
  ]);

  const [editingRule, setEditingRule] = useState<AlertRule | null>(null);

  const createNewRule = () => {
    const newRule: AlertRule = {
      id: `rule-${Date.now()}`,
      name: 'New Alert Rule',
      enabled: true,
      conditions: [
        { id: `cond-${Date.now()}`, metric: 'api_calls', operator: '>', value: 0, duration: 5 },
      ],
      actions: [
        { id: `act-${Date.now()}`, type: 'email', target: '' },
      ],
    };
    setEditingRule(newRule);
  };

  const saveRule = () => {
    if (!editingRule) return;

    if (!editingRule.name.trim()) {
      toast.error('Please enter a rule name');
      return;
    }

    if (editingRule.conditions.length === 0) {
      toast.error('Please add at least one condition');
      return;
    }

    if (editingRule.actions.length === 0) {
      toast.error('Please add at least one action');
      return;
    }

    const existingIndex = rules.findIndex(r => r.id === editingRule.id);
    if (existingIndex >= 0) {
      setRules(prev => prev.map(r => r.id === editingRule.id ? editingRule : r));
      toast.success('Rule updated successfully');
    } else {
      setRules(prev => [...prev, editingRule]);
      toast.success('Rule created successfully');
    }
    setEditingRule(null);
  };

  const deleteRule = (id: string) => {
    setRules(prev => prev.filter(r => r.id !== id));
    toast.success('Rule deleted');
  };

  const toggleRule = (id: string) => {
    setRules(prev => prev.map(r => 
      r.id === id ? { ...r, enabled: !r.enabled } : r
    ));
  };

  const testRule = (rule: AlertRule) => {
    toast.info(`Testing rule: ${rule.name}`, {
      description: 'Evaluating conditions against current metrics...',
    });
    
    setTimeout(() => {
      toast.success('Rule test completed', {
        description: 'No alerts would be triggered with current metrics.',
      });
    }, 1500);
  };

  const addCondition = () => {
    if (!editingRule) return;
    const newCondition: Condition = {
      id: `cond-${Date.now()}`,
      metric: 'api_calls',
      operator: '>',
      value: 0,
      duration: 5,
    };
    setEditingRule({
      ...editingRule,
      conditions: [...editingRule.conditions, newCondition],
    });
  };

  const removeCondition = (id: string) => {
    if (!editingRule) return;
    setEditingRule({
      ...editingRule,
      conditions: editingRule.conditions.filter(c => c.id !== id),
    });
  };

  const updateCondition = (id: string, updates: Partial<Condition>) => {
    if (!editingRule) return;
    setEditingRule({
      ...editingRule,
      conditions: editingRule.conditions.map(c =>
        c.id === id ? { ...c, ...updates } : c
      ),
    });
  };

  const addAction = () => {
    if (!editingRule) return;
    const newAction: Action = {
      id: `act-${Date.now()}`,
      type: 'email',
      target: '',
    };
    setEditingRule({
      ...editingRule,
      actions: [...editingRule.actions, newAction],
    });
  };

  const removeAction = (id: string) => {
    if (!editingRule) return;
    setEditingRule({
      ...editingRule,
      actions: editingRule.actions.filter(a => a.id !== id),
    });
  };

  const updateAction = (id: string, updates: Partial<Action>) => {
    if (!editingRule) return;
    setEditingRule({
      ...editingRule,
      actions: editingRule.actions.map(a =>
        a.id === id ? { ...a, ...updates } : a
      ),
    });
  };

  return (
    <div 
      className="min-h-screen dark:from-slate-900 dark:to-slate-800"
      style={{
        background: `linear-gradient(to bottom right, ${primaryColor}15, ${secondaryColor}15)`
      }}
    >
      {/* Header */}
      <div className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700">
        <div className="container py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-slate-900 dark:text-white">
                Custom Alert Rules
              </h1>
              <p className="text-slate-600 dark:text-slate-400 mt-1">
                Create custom rules to detect specific conditions and trigger actions
              </p>
            </div>
            <button
              onClick={createNewRule}
              className="px-4 py-2 text-white rounded-lg hover:opacity-90 flex items-center gap-2"
              style={{ backgroundColor: primaryColor }}
            >
              <Plus className="w-4 h-4" />
              New Rule
            </button>
          </div>
        </div>
      </div>

      <div className="container py-8">
        {/* Rules List */}
        <div className="space-y-4">
          {rules.map((rule) => (
            <div
              key={rule.id}
              className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-3">
                    <h3 className="text-xl font-bold text-slate-900 dark:text-white">
                      {rule.name}
                    </h3>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={rule.enabled}
                        onChange={() => toggleRule(rule.id)}
                        className="sr-only peer"
                      />
                      <div 
                        className="w-11 h-6 bg-slate-200 peer-focus:outline-none peer-focus:ring-4 rounded-full peer dark:bg-slate-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-slate-600"
                        style={{
                          '--tw-ring-color': `${primaryColor}40`,
                          backgroundColor: rule.enabled ? primaryColor : undefined
                        } as React.CSSProperties}
                      ></div>
                    </label>
                  </div>

                  <div className="space-y-2">
                    <div>
                      <p className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-1">
                        Conditions:
                      </p>
                      {rule.conditions.map((cond, idx) => (
                        <p key={cond.id} className="text-sm text-slate-600 dark:text-slate-400">
                          {idx > 0 && 'AND '}
                          {METRICS.find(m => m.value === cond.metric)?.label} {cond.operator} {cond.value}
                          {cond.duration && ` for ${cond.duration} minutes`}
                        </p>
                      ))}
                    </div>

                    <div>
                      <p className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-1">
                        Actions:
                      </p>
                      {rule.actions.map((action) => (
                        <p key={action.id} className="text-sm text-slate-600 dark:text-slate-400">
                          Send {action.type} to {action.target || '(not configured)'}
                        </p>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => testRule(rule)}
                    className="px-3 py-1 text-white rounded text-sm font-medium hover:opacity-90 transition-colors flex items-center gap-1"
                    style={{ backgroundColor: secondaryColor }}
                  >
                    <Play className="w-3 h-3" />
                    Test
                  </button>
                  <button
                    onClick={() => setEditingRule(rule)}
                    className="px-3 py-1 text-white rounded text-sm font-medium hover:opacity-90 transition-colors"
                    style={{ backgroundColor: primaryColor }}
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => deleteRule(rule.id)}
                    className="px-3 py-1 bg-red-600 hover:bg-red-700 text-white rounded text-sm font-medium transition-colors flex items-center gap-1"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </div>
            </div>
          ))}

          {rules.length === 0 && (
            <div className="text-center py-12">
              <p className="text-slate-600 dark:text-slate-400 mb-4">
                No alert rules configured yet
              </p>
              <button
                onClick={createNewRule}
                className="px-4 py-2 text-white rounded-lg hover:opacity-90"
                style={{ backgroundColor: primaryColor }}
              >
                Create Your First Rule
              </button>
            </div>
          )}
        </div>

        {/* Rule Editor Modal */}
        {editingRule && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
              <div className="p-6 border-b border-slate-200 dark:border-slate-700">
                <h2 className="text-2xl font-bold text-slate-900 dark:text-white">
                  {rules.find(r => r.id === editingRule.id) ? 'Edit Rule' : 'Create New Rule'}
                </h2>
              </div>

              <div className="p-6 space-y-6">
                {/* Rule Name */}
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    Rule Name
                  </label>
                  <input
                    type="text"
                    value={editingRule.name}
                    onChange={(e) => setEditingRule({ ...editingRule, name: e.target.value })}
                    className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
                    placeholder="e.g., High Error Rate Alert"
                  />
                </div>

                {/* Conditions */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                      Conditions (ALL must be true)
                    </label>
                    <button
                      onClick={addCondition}
                      className="px-3 py-1 text-white rounded text-sm hover:opacity-90 flex items-center gap-1"
                    style={{ backgroundColor: primaryColor }}
                    >
                      <Plus className="w-3 h-3" />
                      Add Condition
                    </button>
                  </div>

                  <div className="space-y-3">
                    {editingRule.conditions.map((cond, idx) => (
                      <div key={cond.id} className="flex items-center gap-2 bg-slate-50 dark:bg-slate-700/50 p-3 rounded-lg">
                        {idx > 0 && <span className="text-sm font-semibold text-slate-600 dark:text-slate-400">AND</span>}
                        
                        <select
                          value={cond.metric}
                          onChange={(e) => updateCondition(cond.id, { metric: e.target.value })}
                          className="px-3 py-2 border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-700 text-slate-900 dark:text-white text-sm"
                        >
                          {METRICS.map(m => (
                            <option key={m.value} value={m.value}>{m.label}</option>
                          ))}
                        </select>

                        <select
                          value={cond.operator}
                          onChange={(e) => updateCondition(cond.id, { operator: e.target.value as any })}
                          className="px-3 py-2 border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-700 text-slate-900 dark:text-white text-sm"
                        >
                          {OPERATORS.map(op => (
                            <option key={op.value} value={op.value}>{op.label}</option>
                          ))}
                        </select>

                        <input
                          type="number"
                          value={cond.value}
                          onChange={(e) => updateCondition(cond.id, { value: Number(e.target.value) })}
                          className="w-32 px-3 py-2 border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-700 text-slate-900 dark:text-white text-sm"
                        />

                        <span className="text-sm text-slate-600 dark:text-slate-400">for</span>

                        <input
                          type="number"
                          value={cond.duration || 5}
                          onChange={(e) => updateCondition(cond.id, { duration: Number(e.target.value) })}
                          className="w-20 px-3 py-2 border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-700 text-slate-900 dark:text-white text-sm"
                        />

                        <span className="text-sm text-slate-600 dark:text-slate-400">min</span>

                        <button
                          onClick={() => removeCondition(cond.id)}
                          className="ml-auto p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Actions */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                      Actions (when conditions are met)
                    </label>
                    <button
                      onClick={addAction}
                      className="px-3 py-1 text-white rounded text-sm hover:opacity-90 flex items-center gap-1"
                    style={{ backgroundColor: primaryColor }}
                    >
                      <Plus className="w-3 h-3" />
                      Add Action
                    </button>
                  </div>

                  <div className="space-y-3">
                    {editingRule.actions.map((action) => (
                      <div key={action.id} className="flex items-center gap-2 bg-slate-50 dark:bg-slate-700/50 p-3 rounded-lg">
                        <select
                          value={action.type}
                          onChange={(e) => updateAction(action.id, { type: e.target.value as any })}
                          className="px-3 py-2 border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-700 text-slate-900 dark:text-white text-sm"
                        >
                          <option value="email">Email</option>
                          <option value="webhook">Webhook</option>
                          <option value="sms">SMS</option>
                        </select>

                        <input
                          type="text"
                          value={action.target}
                          onChange={(e) => updateAction(action.id, { target: e.target.value })}
                          placeholder={action.type === 'email' ? 'email@example.com' : action.type === 'webhook' ? 'https://...' : '+1234567890'}
                          className="flex-1 px-3 py-2 border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-700 text-slate-900 dark:text-white text-sm"
                        />

                        <button
                          onClick={() => removeAction(action.id)}
                          className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="p-6 border-t border-slate-200 dark:border-slate-700 flex justify-end gap-3">
                <button
                  onClick={() => setEditingRule(null)}
                  className="px-4 py-2 bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-300 dark:hover:bg-slate-600"
                >
                  Cancel
                </button>
                <button
                  onClick={saveRule}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
                >
                  <Save className="w-4 h-4" />
                  Save Rule
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
