import { CreditCard, Plus, Search, Filter, Download, MoreVertical, Lock, Unlock, Eye, Activity } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useState, useEffect, useMemo } from "react";
import { toast } from 'sonner';
import apiClient from '@/services/api';
import { useTenantBranding } from '@/contexts/TenantBrandingContext';
import { exportToExcel } from '@/lib/exportUtils';

interface CardData {
  id: number;
  tenant_id: string;
  card_id: string;
  card_number: string;
  card_type: string;
  customer_id: string;
  account_id: string;
  name_on_card: string;
  expiry_date: string;
  cvv?: string;
  pin_hash?: string | null;
  status: string;
  daily_limit: number;
  monthly_limit: number;
  daily_spent: number;
  monthly_spent: number;
  created_at: string;
  [key: string]: any;
}

interface CardsResponse {
  cards: CardData[];
  total: number;
  message?: string;
  [key: string]: any;
}

export default function AdminCards() {
  const { primaryColor } = useTenantBranding();
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [cards, setCards] = useState<CardData[]>([]);
  const [cardsLoading, setCardsLoading] = useState(true);
  const [processingIds, setProcessingIds] = useState<Set<string>>(new Set());

  // Fetch cards function
  const fetchCards = async (setLoading = true) => {
    if (setLoading) {
      setCardsLoading(true);
    }
    try {
      const response = await apiClient.get<CardsResponse>(`/card/api/v1/cards/tenant`);
      const data = response.data;
      
        // Handle response structure
        let cardsData: CardData[] = [];
        if (Array.isArray(data)) {
          cardsData = data;
        } else if (Array.isArray(data.cards)) {
          cardsData = data.cards;
        } else if (Array.isArray(data.data)) {
          cardsData = data.data;
        }
      
      setCards(cardsData);
    } catch (error: any) {
      console.error('Error fetching cards:', error);
      const errorMessage = error?.response?.data?.message || error?.message || 'Failed to fetch cards';
      if (setLoading) {
        toast.error(errorMessage);
      }
      setCards([]);
    } finally {
      if (setLoading) {
        setCardsLoading(false);
      }
    }
  };

  // Fetch cards on mount and set up auto-refresh
  useEffect(() => {
    fetchCards(true);
    // Refresh every 10 seconds (silently in background)
    const interval = setInterval(() => fetchCards(false), 10000);
    return () => clearInterval(interval);
  }, []);

  // Filter cards
  const filteredCards = useMemo(() => {
    return cards.filter((card) => {
      const cardNumber = card.card_number || '';
      const nameOnCard = card.name_on_card || '';
      const cardId = card.card_id || '';
      const customerId = card.customer_id || '';
      
      const matchesSearch = !searchTerm ||
        nameOnCard.toLowerCase().includes(searchTerm.toLowerCase()) ||
        cardNumber.toLowerCase().includes(searchTerm.toLowerCase()) ||
        cardId.toLowerCase().includes(searchTerm.toLowerCase()) ||
        customerId.toLowerCase().includes(searchTerm.toLowerCase());
      
      const cardStatus = (card.status || '').toLowerCase();
      const matchesStatus = filterStatus === 'all' || cardStatus === filterStatus.toLowerCase();
      
      return matchesSearch && matchesStatus;
    });
  }, [cards, searchTerm, filterStatus]);

  // Get unique statuses for filter
  const uniqueStatuses = useMemo(() => {
    const statuses = new Set<string>();
    cards.forEach(card => {
      if (card.status) {
        statuses.add(card.status.toLowerCase());
      }
    });
    return Array.from(statuses);
  }, [cards]);

  // Calculate statistics
  const stats = useMemo(() => {
    const total = cards.length;
    const active = cards.filter(card => {
      const status = (card.status || '').toLowerCase();
      return status === 'active' || status === 'open';
    }).length;
    const blocked = cards.filter(card => {
      const status = (card.status || '').toLowerCase();
      return status === 'blocked' || status === 'closed';
    }).length;
    const suspended = cards.filter(card => {
      const status = (card.status || '').toLowerCase();
      return status === 'suspended' || status === 'inactive';
    }).length;

    return [
      { label: 'Total Cards', value: total.toLocaleString(), change: '', trend: 'up' as const },
      { label: 'Active Cards', value: active.toLocaleString(), change: '', trend: 'up' as const },
      { label: 'Blocked Cards', value: blocked.toLocaleString(), change: '', trend: 'down' as const },
      { label: 'Suspended Cards', value: suspended.toLocaleString(), change: '', trend: 'down' as const },
    ];
  }, [cards]);

  // Block card
  const handleBlockCard = async (cardId: string) => {
    if (processingIds.has(cardId)) return;
    
    setProcessingIds(prev => new Set(prev).add(cardId));
    
    try {
      await apiClient.post(`/card/api/v1/cards/${cardId}/block`);
      toast.success('Card blocked successfully');
      await fetchCards(false);
    } catch (error: any) {
      console.error('Error blocking card:', error);
      const errorMessage = error?.response?.data?.message || error?.message || 'Failed to block card';
      toast.error(errorMessage);
    } finally {
      setProcessingIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(cardId);
        return newSet;
      });
    }
  };

  // Unblock card
  const handleUnblockCard = async (cardId: string) => {
    if (processingIds.has(cardId)) return;
    
    setProcessingIds(prev => new Set(prev).add(cardId));
    
    try {
      await apiClient.post(`/card/api/v1/cards/${cardId}/unblock`);
      toast.success('Card unblocked successfully');
      await fetchCards(false);
    } catch (error: any) {
      console.error('Error unblocking card:', error);
      const errorMessage = error?.response?.data?.message || error?.message || 'Failed to unblock card';
      toast.error(errorMessage);
    } finally {
      setProcessingIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(cardId);
        return newSet;
      });
    }
  };

  const handleExportExcel = () => {
    const data = filteredCards.map(card => ({
      'Card ID': card.card_id,
      'Card Number': card.card_number,
      'Name on Card': card.name_on_card,
      'Customer ID': card.customer_id,
      'Account ID': card.account_id,
      'Card Type': card.card_type,
      'Status': card.status,
      'Daily Limit': `₦${card.daily_limit.toLocaleString()}`,
      'Monthly Limit': `₦${card.monthly_limit.toLocaleString()}`,
      'Daily Spent': `₦${card.daily_spent.toLocaleString()}`,
      'Monthly Spent': `₦${card.monthly_spent.toLocaleString()}`,
      'Expiry Date': card.expiry_date,
      'Created': card.created_at,
    }));
    exportToExcel(data, 'cards');
  };

  const getStatusColor = (status: string) => {
    const statusLower = (status || '').toLowerCase();
    if (statusLower === 'active' || statusLower === 'open') {
      return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300';
    }
    if (statusLower === 'blocked' || statusLower === 'closed') {
      return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300';
    }
    if (statusLower === 'suspended' || statusLower === 'inactive') {
      return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300';
    }
    return 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300';
  };

  const getTypeColor = (type: string) => {
    const typeLower = (type || '').toLowerCase();
    if (typeLower === 'virtual') {
      return 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300';
    } else if (typeLower === 'physical') {
      return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300';
    }
    return 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300';
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-purple-50 dark:from-slate-900 dark:via-slate-900 dark:to-slate-900">
      {/* Header */}
      <div className="border-b border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-sm">
        <div className="container py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
                <CreditCard className="w-8 h-8" style={{ color: primaryColor }} />
                Card Management
              </h1>
              <p className="text-slate-600 dark:text-slate-400 mt-1">
                Manage debit and credit cards across all banks
              </p>
            </div>
            <Button className="gap-2">
              <Plus className="w-4 h-4" />
              Issue New Card
            </Button>
          </div>
        </div>
      </div>

      <div className="container py-8 space-y-8">
        {/* Statistics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {stats.map((stat) => (
            <Card key={stat.label}>
              <CardHeader className="pb-2">
                <CardDescription>{stat.label}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stat.value}</div>
                <p
                  className={`text-xs mt-1 ${
                    stat.trend === 'up' ? 'text-green-600' : 'text-red-600'
                  }`}
                >
                  {stat.change} from last month
                </p>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Cards Table */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Card Registry</CardTitle>
                <CardDescription>All issued cards in the system</CardDescription>
              </div>
              <div className="flex items-center gap-3">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <Input
                    placeholder="Search cards..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-9 w-64"
                  />
                </div>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" size="icon">
                      <Filter className="w-4 h-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuLabel>Filter by Status</DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={() => setFilterStatus('all')}>
                      All Cards
                    </DropdownMenuItem>
                    {uniqueStatuses.map(status => (
                      <DropdownMenuItem key={status} onClick={() => setFilterStatus(status)}>
                        {status.charAt(0).toUpperCase() + status.slice(1)}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
                <Button variant="outline" size="icon" onClick={handleExportExcel} disabled={cardsLoading}>
                  <Download className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Card Number</TableHead>
                  <TableHead>Name on Card</TableHead>
                  <TableHead>Customer ID</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Daily Limit</TableHead>
                  <TableHead>Monthly Limit</TableHead>
                  <TableHead>Expiry</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {cardsLoading ? (
                  <TableRow>
                    <TableCell colSpan={9} className="text-center py-12">
                      <Activity className="w-8 h-8 animate-spin mx-auto mb-2" style={{ color: primaryColor }} />
                      <p className="text-slate-600 dark:text-slate-400">Loading cards...</p>
                    </TableCell>
                  </TableRow>
                ) : filteredCards.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={9} className="text-center py-12">
                      <CreditCard className="w-8 h-8 mx-auto mb-2 text-slate-400" />
                      <p className="text-slate-600 dark:text-slate-400">No cards found</p>
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredCards.map((card) => {
                    const cardId = card.card_id;
                    const isProcessing = processingIds.has(cardId);
                    const cardStatus = (card.status || '').toLowerCase();
                    const isBlocked = cardStatus === 'blocked' || cardStatus === 'closed';

                    return (
                      <TableRow key={card.id}>
                        <TableCell className="font-mono">{card.card_number}</TableCell>
                        <TableCell className="font-medium">{card.name_on_card}</TableCell>
                        <TableCell className="font-mono text-sm">{card.customer_id}</TableCell>
                        <TableCell>
                          <Badge variant="secondary" className={getTypeColor(card.card_type)}>
                            {card.card_type.charAt(0).toUpperCase() + card.card_type.slice(1)}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary" className={getStatusColor(card.status)}>
                            {card.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-slate-600 dark:text-slate-400">
                          ₦{card.daily_limit.toLocaleString()}
                          {card.daily_spent > 0 && (
                            <span className="block text-xs text-slate-500">
                              Spent: ₦{card.daily_spent.toLocaleString()}
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="text-slate-600 dark:text-slate-400">
                          ₦{card.monthly_limit.toLocaleString()}
                          {card.monthly_spent > 0 && (
                            <span className="block text-xs text-slate-500">
                              Spent: ₦{card.monthly_spent.toLocaleString()}
                            </span>
                          )}
                        </TableCell>
                        <TableCell>{new Date(card.expiry_date).toLocaleDateString()}</TableCell>
                        <TableCell>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon" disabled={isProcessing}>
                                {isProcessing ? (
                                  <Activity className="w-4 h-4 animate-spin" />
                                ) : (
                                  <MoreVertical className="w-4 h-4" />
                                )}
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem>
                                <Eye className="w-4 h-4 mr-2" />
                                View Details
                              </DropdownMenuItem>
                              {!isBlocked ? (
                                <DropdownMenuItem
                                  onClick={() => handleBlockCard(cardId)}
                                  disabled={isProcessing}
                                >
                                  <Lock className="w-4 h-4 mr-2" />
                                  Block Card
                                </DropdownMenuItem>
                              ) : (
                                <DropdownMenuItem
                                  onClick={() => handleUnblockCard(cardId)}
                                  disabled={isProcessing}
                                >
                                  <Unlock className="w-4 h-4 mr-2" />
                                  Unblock Card
                                </DropdownMenuItem>
                              )}
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
