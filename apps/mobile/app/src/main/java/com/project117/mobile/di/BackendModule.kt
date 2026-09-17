package com.project117.mobile.di

import com.project117.mobile.data.backend.DynamicFieldBackend
import com.project117.mobile.domain.backend.FieldBackend
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class BackendModule {

    @Binds
    @Singleton
    abstract fun bindFieldBackend(impl: DynamicFieldBackend): FieldBackend
}
