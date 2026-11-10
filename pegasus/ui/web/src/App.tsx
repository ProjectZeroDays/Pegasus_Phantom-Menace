import { Route, Switch } from "wouter";
import { AppProvider } from "@/state/AppContext";
import { AppShell } from "@/components/layout/AppShell";

import MissionControl from "@/pages/MissionControl";
import Devices from "@/pages/Devices";
import SocialMedia from "@/pages/SocialMedia";
import RelayDashboard from "@/pages/RelayDashboard";
import Pwa from "@/pages/Pwa";
import Tenant from "@/pages/Tenant";
import Webhooks from "@/pages/Webhooks";
import SocialEngineering from "@/pages/SocialEngineering";
import Monitoring from "@/pages/Monitoring";
import AccessWorkflow from "@/pages/AccessWorkflow";
import WorkflowEngine from "@/pages/WorkflowEngine";
import ZeroClick from "@/pages/ZeroClick";
import Delivery from "@/pages/Delivery";
import Capabilities from "@/pages/Capabilities";
import PhysicalOps from "@/pages/PhysicalOps";
import FastbootOps from "@/pages/FastbootOps";
import C2Dashboard from "@/pages/C2Dashboard";
import PostExploit from "@/pages/PostExploit";
import Locations from "@/pages/Locations";
import Geofences from "@/pages/Geofences";
import Calls from "@/pages/Calls";
import Contacts from "@/pages/Contacts";
import Messages from "@/pages/Messages";
import Browser from "@/pages/Browser";
import Apps from "@/pages/Apps";
import Media from "@/pages/Media";
import WifiNetworks from "@/pages/Wifi";
import Keylog from "@/pages/Keylog";
import ActivityTimeline from "@/pages/ActivityTimeline";
import Keywords from "@/pages/Keywords";
import PayloadFactory from "@/pages/PayloadFactory";
import Payloads from "@/pages/Payloads";
import Wordlists from "@/pages/Wordlists";
import Sessions from "@/pages/Sessions";
import Campaigns from "@/pages/Campaigns";
import Reports from "@/pages/Reports";
import NetworkDashboard from "@/pages/NetworkDashboard";
import Toolbox from "@/pages/Toolbox";
import Skills from "@/pages/Skills";
import Plugins from "@/pages/Plugins";
import CommandCenter from "@/pages/CommandCenter";
import Settings from "@/pages/Settings";
import Autonomous from "@/pages/Autonomous";
import Setup from "@/pages/Setup";
import Logs from "@/pages/Logs";
import LogsDashboard from "@/pages/LogsDashboard";
import AdminUsers from "@/pages/AdminUsers";
import NotFound from "@/pages/NotFound";
import Login from "@/pages/Login";
import AdminLogin from "@/pages/AdminLogin";
import Wallets from "@/pages/Wallets";
import Vault from "@/pages/Vault";
import Wiki from "@/pages/Wiki";
import Help from "@/pages/Help";
import HowTo from "@/pages/HowTo";
import BugReport from "@/pages/BugReport";
import Privacy from "@/pages/Privacy";
import Tunnels from "@/pages/Tunnels";
import CveFramework from "@/pages/CveFramework";
import Kyc from "@/pages/Kyc";
import Osint from "@/pages/Osint";

export default function App() {
  return (
    <AppProvider>
      <AppShell>
        <Switch>
          <Route path="/" component={MissionControl} />
          <Route path="/devices" component={Devices} />
          <Route path="/monitoring" component={Monitoring} />
          <Route path="/access" component={AccessWorkflow} />
          <Route path="/workflows" component={WorkflowEngine} />
          <Route path="/zero-click" component={ZeroClick} />
          <Route path="/delivery" component={Delivery} />
          <Route path="/cve" component={ZeroClick} />
          <Route path="/post-exploit" component={PostExploit} />
          <Route path="/capabilities" component={Capabilities} />
<Route path="/physical" component={PhysicalOps} />
<Route path="/fastboot" component={FastbootOps} />
          <Route path="/c2" component={C2Dashboard} />
          <Route path="/locations" component={Locations} />
          <Route path="/geofences" component={Geofences} />
          <Route path="/calls" component={Calls} />
          <Route path="/contacts" component={Contacts} />
          <Route path="/messages" component={Messages} />
          <Route path="/browser" component={Browser} />
          <Route path="/apps" component={Apps} />
          <Route path="/media" component={Media} />
          <Route path="/wifi" component={WifiNetworks} />
          <Route path="/keylog" component={Keylog} />
          <Route path="/activity" component={ActivityTimeline} />
          <Route path="/keywords" component={Keywords} />
          <Route path="/payload-factory" component={PayloadFactory} />
<Route path="/payloads" component={Payloads} />
          <Route path="/wordlists" component={Wordlists} />
          <Route path="/sessions" component={Sessions} />
          <Route path="/campaigns" component={Campaigns} />
          <Route path="/reports" component={Reports} />
          <Route path="/network-dashboard" component={NetworkDashboard} />
          <Route path="/tools" component={Toolbox} />
          <Route path="/skills" component={Skills} />
          <Route path="/plugins" component={Plugins} />
          <Route path="/commands" component={CommandCenter} />
          <Route path="/settings" component={Settings} />
          <Route path="/autonomous" component={Autonomous} />
          <Route path="/setup" component={Setup} />
          <Route path="/logs" component={Logs} />
          <Route path="/logs-dashboard" component={LogsDashboard} />
          <Route path="/admin-users" component={AdminUsers} />
          <Route path="/social" component={SocialMedia} />
          <Route path="/relay" component={RelayDashboard} />
          <Route path="/pwa" component={Pwa} />
          <Route path="/tenants" component={Tenant} />
          <Route path="/webhooks" component={Webhooks} />
          <Route path="/social-engineering" component={SocialEngineering} />
          <Route path="/login" component={Login} />
          <Route path="/admin-login" component={AdminLogin} />
          <Route path="/wallets" component={Wallets} />
          <Route path="/vault" component={Vault} />
          <Route path="/wiki" component={Wiki} />
          <Route path="/help" component={Help} />
          <Route path="/howto" component={HowTo} />
          <Route path="/bug-report" component={BugReport} />
          <Route path="/privacy" component={Privacy} />
          <Route path="/tunnels" component={Tunnels} />
          <Route path="/cve-framework" component={CveFramework} />
          <Route path="/kyc" component={Kyc} />
          <Route path="/osint" component={Osint} />
          <Route component={NotFound} />
        </Switch>
      </AppShell>
    </AppProvider>
  );
}
