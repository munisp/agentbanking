import { NextFunction, Request, Response } from "express";
import createLogger from "../config/logger.config";
import { extract_name_form_path } from "../utils/helpers";

const logger = createLogger(extract_name_form_path(__filename));

const processInput = async (req: Request, contentType: string) => {
  return new Promise<void>((response) => {
    let rawBody = "";

    // Collect the raw body data
    req.on("data", (chunk) => {
      rawBody += chunk;
    });

    req.on("end", () => {
      try {
        console.log("Body Collected, attempt to parse", rawBody);
        // Parse the raw body into JSON (or any other format you need)
        const parsedBody = JSON.parse(rawBody);

        console.log("parsed body", parsedBody);

        // Optionally, handle versioning if needed
        const version = contentType.split("version=")[1];
        if (version) {
          parsedBody.content_type_version = version; // Attach version to the parsed body
        }

        // Attach the parsed body to the request object
        req.body = parsedBody;
      } catch (error) {
        logger.error("error parsing", error);
      } finally {
        response();
      }
    });
  });
};

export const customMojaloopJsonParser = async (
  req: Request,
  res: Response,
  next: NextFunction
) => {
  const contentType = req.headers["content-type"];

  console.log("customMojaloopJsonParser ", contentType);

  if (
    contentType &&
    (contentType.includes("application/vnd.interoperability.parties+json") ||
      contentType.includes(
        "application/vnd.interoperability.participants+json"
      ) ||
      contentType.includes("application/vnd.interoperability.quotes+json") ||
      contentType.includes("application/vnd.interoperability.transfers+json"))
  ) {
    await processInput(req, contentType);
  }

  next();
};

export const setMojaloopRequiredHeaders = (
  req: Request,
  res: Response,
  next: NextFunction
) => {
  const accept_header = req.headers["accept"];

  if (accept_header) {
    res.setHeader("content-type", accept_header);
  }

  res.setHeader("date", new Date().toISOString());

  next();
};
