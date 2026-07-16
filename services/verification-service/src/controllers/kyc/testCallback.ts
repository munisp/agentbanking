import { asyncHandler } from "../../middlewares/async";

export const testCallback = asyncHandler(async (req, res) => {
  console.log(req.body);
  return res.status(200).json({});
});
