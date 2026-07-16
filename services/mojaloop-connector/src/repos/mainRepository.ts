import httpStatus from "http-status";
import { AppDataSource } from "../database/dataSource";
import {
  EntityManager,
  EntityTarget,
  FindManyOptions,
  FindOneOptions,
  FindOptionsRelations,
  FindOptionsSelect,
  FindOptionsWhere,
  In,
  ObjectLiteral,
  Repository,
} from "typeorm";
import ApiError from "../utils/ApiError";

export interface ICheckEntityExistence<T> {
  clause: FindOneOptions<T>;
  shouldExist: boolean;
  message?: string;
}

export class MainRepository<T extends ObjectLiteral> {
  public readonly AppDataSource = AppDataSource;
  public readonly Entity: EntityTarget<T>;
  public readonly repo: Repository<T>;

  public constructor(Entity: EntityTarget<T>) {
    this.Entity = Entity;
    this.repo = AppDataSource.manager.getRepository(Entity);
  }

  private identifyChild() {
    return this.Entity.toString();
  }

  public getMetadata() {
    return this.AppDataSource.getMetadata(this.Entity);
  }

  public async getOne({
    id,
    key = "id",
    relations,
    select,
  }: {
    id: number | string;
    key?: keyof T;
    relations?: FindOptionsRelations<T>;
    select?: FindOptionsSelect<T>;
  }) {
    return await this.AppDataSource.manager.findOne(this.Entity, {
      where: {
        [key]: id,
      },
      relations,
      select,
    } as FindOneOptions<T>);
  }

  public async checkEntityExistence({
    clause,
    shouldExist,
    message,
  }: ICheckEntityExistence<T>) {
    const entity = await this.AppDataSource!.manager.findOne(
      this.Entity,
      clause
    );

    if (!shouldExist && entity)
      throw new ApiError(
        httpStatus.CONFLICT,
        message || `${this.identifyChild()} already exists.`
      );

    if (shouldExist && !entity)
      throw new ApiError(
        httpStatus.NOT_FOUND,
        message || `${this.identifyChild()} does not exist.`
      );

    return entity;
  }

  public async deleteIfExist(where: FindOptionsWhere<T>, key: keyof T = "id") {
    const entity = await this.repo.findOne({
      where,
      select: [key],
    });

    if (entity) {
      await this.repo.remove(entity);
    }
  }

  public async deleteMultiple(ids: number[], key: keyof T = "id") {
    const entities = await this.repo.find({
      where: {
        [key]: In(ids),
      } as FindOptionsWhere<T>,
      select: [key],
    });

    if (entities.length > 0) {
      await this.repo.remove(entities);
    }
  }

  public async saveEntity(entity: T) {
    return await this.AppDataSource.manager.save(entity);
  }

  public async find(options?: FindManyOptions<T>) {
    return await this.repo.find(options);
  }

  public async paginatedFind(options?: FindManyOptions<T>) {
    return await this.AppDataSource.manager.findAndCount(this.Entity, options);
  }

  public getRepo() {
    return this.AppDataSource.getRepository(this.Entity);
  }

  public getRepoForManager(manager: EntityManager) {
    return manager.getRepository(this.Entity);
  }

  public async getOneWhere(options: FindOneOptions<T>, error?: Error) {
    const entity = await this.repo.findOne(options);
    if (!entity) {
      throw error ?? new ApiError(httpStatus.NOT_FOUND, "Not found");
    }
    return entity;
  }
}
