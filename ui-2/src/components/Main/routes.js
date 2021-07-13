import { Dashboard } from "@material-ui/icons";
import DashboardPage from "./views/Dashboard";
import Person from "@material-ui/icons/Person";
import ProductPage from "./views/Product";
import EngagementsPage from "./views/Engagements";
import InboxIcon from "@material-ui/icons/Inbox";
import { IconButton } from "@material-ui/core";
const dashboardRouters = [
  {
    path: "/dashboard",
    name: "Dashboard",
    icon: Dashboard,
    component: DashboardPage,
  },
  {
    path: "/product",
    name: "Product",
    icon: Person,
    component: ProductPage,
  },
  // {
  //   path: "/engagements",
  //   name: "Engagements",
  //   component: EngagementsPage,
  // },
  {
    path: "/engagements",
    name: "Engagements",
    icon: InboxIcon,
    component: EngagementsPage,
  },
];
export default dashboardRouters;
