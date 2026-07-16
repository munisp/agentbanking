import httpStatus from "http-status";
import { AppDataSource } from "../../database/dataSource";
import { ClientEntity } from "../../entity/ClientEntity";
import { asyncHandler } from "../../middlewares/async";
import { ApiError } from "../../middlewares/error";

export const getClient = asyncHandler(async (req, res) => {
  const id = req.params.id;

  const client = await AppDataSource.manager.findOne(ClientEntity, {
    where: { client_id: id },
  });

  if (!client)
    throw new ApiError(
      httpStatus.NOT_FOUND,
      "Client not found.",
      "VER-404-00",
      "verification-service",
    );

  return res.status(httpStatus.OK).json(client);
});
