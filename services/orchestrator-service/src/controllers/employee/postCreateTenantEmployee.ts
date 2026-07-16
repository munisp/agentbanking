import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { validateRequest } from "../../validations";
import { CreateEmployeeSchema } from "../../validations/schemas";

export const postCreateTenantEmployee = asyncHandler(async (req, res) => {
  const payload = validateRequest(CreateEmployeeSchema, req.body);
  return res.status(httpStatus.CREATED).json({ message: "success" });
});
