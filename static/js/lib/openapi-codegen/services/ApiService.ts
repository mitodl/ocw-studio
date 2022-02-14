/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { Website } from '../models/Website';
import type { WebsiteDetail } from '../models/WebsiteDetail';
import type { WebsiteStarter } from '../models/WebsiteStarter';
import type { WebsiteStarterDetail } from '../models/WebsiteStarterDetail';
import type { WebsiteWrite } from '../models/WebsiteWrite';

import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';

export class ApiService {

    /**
     * Viewset for Websites
     * @param limit Number of results to return per page.
     * @param offset The initial index from which to return the results.
     * @returns any
     * @throws ApiError
     */
    public static listWebsites(
        limit?: number,
        offset?: number,
    ): CancelablePromise<{
        count?: number;
        next?: string | null;
        previous?: string | null;
        results?: Array<Website>;
    }> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/api/websites/',
            query: {
                'limit': limit,
                'offset': offset,
            },
        });
    }

    /**
     * Viewset for Websites
     * @param requestBody
     * @returns WebsiteWrite
     * @throws ApiError
     */
    public static createWebsiteWrite(
        requestBody?: WebsiteWrite,
    ): CancelablePromise<WebsiteWrite> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/api/websites/',
            body: requestBody,
            mediaType: 'application/json',
        });
    }

    /**
     * Viewset for Websites
     * @param name
     * @returns WebsiteDetail
     * @throws ApiError
     */
    public static retrieveWebsiteDetail(
        name: string,
    ): CancelablePromise<WebsiteDetail> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/api/websites/{name}/',
            path: {
                'name': name,
            },
        });
    }

    /**
     * Viewset for Websites
     * @param name
     * @param requestBody
     * @returns WebsiteDetail
     * @throws ApiError
     */
    public static updateWebsiteDetail(
        name: string,
        requestBody?: WebsiteDetail,
    ): CancelablePromise<WebsiteDetail> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/api/websites/{name}/',
            path: {
                'name': name,
            },
            body: requestBody,
            mediaType: 'application/json',
        });
    }

    /**
     * Viewset for Websites
     * @param name
     * @param requestBody
     * @returns WebsiteDetail
     * @throws ApiError
     */
    public static partialUpdateWebsiteDetail(
        name: string,
        requestBody?: WebsiteDetail,
    ): CancelablePromise<WebsiteDetail> {
        return __request(OpenAPI, {
            method: 'PATCH',
            url: '/api/api/websites/{name}/',
            path: {
                'name': name,
            },
            body: requestBody,
            mediaType: 'application/json',
        });
    }

    /**
     * Viewset for WebsiteStarters
     * @returns WebsiteStarter
     * @throws ApiError
     */
    public static listWebsiteStarters(): CancelablePromise<Array<WebsiteStarter>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/api/starters/',
        });
    }

    /**
     * Viewset for WebsiteStarters
     * @param id
     * @returns WebsiteStarterDetail
     * @throws ApiError
     */
    public static retrieveWebsiteStarterDetail(
        id: string,
    ): CancelablePromise<WebsiteStarterDetail> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/api/starters/{id}/',
            path: {
                'id': id,
            },
        });
    }

    /**
     * Trigger a preview task for the website
     * @param name
     * @param requestBody
     * @returns WebsiteDetail
     * @throws ApiError
     */
    public static previewWebsiteDetail(
        name: string,
        requestBody?: WebsiteDetail,
    ): CancelablePromise<WebsiteDetail> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/api/websites/{name}/preview/',
            path: {
                'name': name,
            },
            body: requestBody,
            mediaType: 'application/json',
        });
    }

    /**
     * Trigger a publish task for the website
     * @param name
     * @param requestBody
     * @returns WebsiteDetail
     * @throws ApiError
     */
    public static publishWebsiteDetail(
        name: string,
        requestBody?: WebsiteDetail,
    ): CancelablePromise<WebsiteDetail> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/api/websites/{name}/publish/',
            path: {
                'name': name,
            },
            body: requestBody,
            mediaType: 'application/json',
        });
    }

    /**
     * Process webhook requests for WebsiteStarter site configs
     * @param requestBody
     * @returns WebsiteStarterDetail
     * @throws ApiError
     */
    public static siteConfigsWebsiteStarterDetail(
        requestBody?: WebsiteStarterDetail,
    ): CancelablePromise<WebsiteStarterDetail> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/api/starters/site_configs/',
            body: requestBody,
            mediaType: 'application/json',
        });
    }

}