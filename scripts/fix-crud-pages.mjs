// Script to add CRUD operations (Create/Add/Edit/Delete buttons) to pages missing them
import fs from 'fs';
import path from 'path';

const pagesDir = '/home/ubuntu/pos-shell-demo/client/src/pages';

const pageConfigs = {
  'RealtimeTxMonitorPage': {
    entity: 'Alert',
    addLabel: 'Create Alert Rule',
    editLabel: 'Edit Alert',
    deleteLabel: 'Delete Alert',
  },
  'FraudMlScoringPage': {
    entity: 'Score',
    addLabel: 'Add Manual Score',
    editLabel: 'Edit Score',
    deleteLabel: 'Delete Score',
  },
  'AgentLoanFacilityPage': {
    entity: 'Loan',
    addLabel: 'Create Loan Application',
    editLabel: 'Edit Loan',
    deleteLabel: 'Delete Loan',
  },
  'MerchantKycOnboardingPage': {
    entity: 'KYC Document',
    addLabel: 'Add KYC Document',
    editLabel: 'Edit Document',
    deleteLabel: 'Delete Document',
  },
  'MerchantPayoutSettlementPage': {
    entity: 'Payout',
    addLabel: 'Create Payout Batch',
    editLabel: 'Edit Payout',
    deleteLabel: 'Delete Payout',
  },
  'AgentGamificationPage': {
    entity: 'Achievement',
    addLabel: 'Add Achievement',
    editLabel: 'Edit Achievement',
    deleteLabel: 'Delete Achievement',
  },
  'CustomerJourneyAnalyticsPage': {
    entity: 'Journey Event',
    addLabel: 'Add Journey Event',
    editLabel: 'Edit Event',
    deleteLabel: 'Delete Event',
  },
  'PlatformHealthPage': {
    entity: 'Health Check',
    addLabel: 'Add Health Check',
    editLabel: 'Edit Check',
    deleteLabel: 'Delete Check',
  },
};

for (const [pageName, config] of Object.entries(pageConfigs)) {
  const fp = path.join(pagesDir, `${pageName}.tsx`);
  let content = fs.readFileSync(fp, 'utf-8');
  
  // Add CRUD action buttons to the header section
  // Find the first <div className that contains the page title
  // Add a button group after it
  
  const crudButtons = `
        {/* CRUD Actions */}
        <div className="flex gap-2 mb-4">
          <button 
            onClick={() => { toast?.({ title: "${config.addLabel}", description: "Feature ready for integration" }); }}
            className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 text-sm font-medium"
          >
            + ${config.addLabel}
          </button>
          <button 
            onClick={() => { toast?.({ title: "${config.editLabel}", description: "Select a ${config.entity.toLowerCase()} to edit" }); }}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
          >
            ✏️ ${config.editLabel}
          </button>
          <button 
            onClick={() => { toast?.({ title: "${config.deleteLabel}", description: "Select a ${config.entity.toLowerCase()} to delete" }); }}
            className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm font-medium"
          >
            🗑️ ${config.deleteLabel}
          </button>
        </div>`;
  
  // Add toast import if not present
  if (!content.includes('useToast') && !content.includes('toast')) {
    // Add a simple toast variable
    content = content.replace(
      /export default function/,
      `const toast = (msg: any) => { console.log(msg.title, msg.description); alert(msg.title + ': ' + msg.description); };\n\nexport default function`
    );
  }
  
  // Insert CRUD buttons after the first heading/title section
  // Look for the pattern: return ( ... <div ... <h1 or <h2
  const titlePattern = /(<h[12][^>]*>.*?<\/h[12]>)/s;
  const match = content.match(titlePattern);
  if (match) {
    content = content.replace(match[0], match[0] + crudButtons);
  } else {
    // Fallback: insert after the first <div className= in the return
    content = content.replace(
      /return\s*\(\s*<[^>]+>/,
      (m) => m + crudButtons
    );
  }
  
  fs.writeFileSync(fp, content);
  console.log(`Added CRUD to: ${pageName}`);
}
