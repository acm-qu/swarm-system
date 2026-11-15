import { History } from '@/components/icons';
import { SoonPage } from '@/components/soon';

export default function HistoryPage() {
  return (
    <SoonPage
      title="History" icon={History}
      about="Connections, who took control, stops, terminal commands and installs."
      needs="The hub doesn't keep a history yet. This page arrives when it does."
    />
  );
}
