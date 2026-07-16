import { Router } from "express";
import { getTenant } from "../controllers/tenant/getTenant";
import { getKeycloakPublicKey } from "../controllers/tenant/getKeycloakPublicKey";
import { getTenantFeatures } from "../controllers/tenant/getTenantFeatures";
import { postCreateBranch } from "../controllers/branch/postCreateBranch";
import { getBranches } from "../controllers/branch/getBranches";
import { getTenants } from "../controllers/tenant/getTenants";
import { getGlobalFeatures } from "../controllers/tenant/getGlobalFeatures";
import { putUpdateTenant } from "../controllers/tenant/putUpdateTenant";
import { postSuspendTenant } from "../controllers/tenant/postSuspendTenant";
import { postUnsuspendTenant } from "../controllers/tenant/postUnsuspendTenant";
import { postSuspendBranch } from "../controllers/branch/postSuspendBranch";
import { postUnsuspendBranch } from "../controllers/branch/postUnsuspendBranch";
import { putUpdateBranch } from "../controllers/branch/putUpdateBranch";

const router = Router();

router.route("/branch").post(postCreateBranch).get(getBranches);

router.route("/branch/:tenant_id/:branch_id").put(putUpdateBranch);

router.route("/branch/:tenant_id/:branch_id/suspend").post(postSuspendBranch);

router.route("/branch/:tenant_id/:branch_id/unsuspend").post(postUnsuspendBranch);


router.route("/features").get(getTenantFeatures);

router.route("/features/global").get(getGlobalFeatures);

router.route("/all").get(getTenants);

router.route("/:tenant_id").get(getTenant);

router.route("/:tenant_id").put(putUpdateTenant);

router.route("/:tenant_id/suspend").post(postSuspendTenant);

router.route("/:tenant_id/unsuspend").post(postUnsuspendTenant);

router.route("/keycloak-public-key/:tenant_id").get(getKeycloakPublicKey);

export default router;
