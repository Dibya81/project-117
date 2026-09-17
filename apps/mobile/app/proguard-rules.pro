# Project 117 — Field Operations, release shrinking rules.

# Moshi reads its adapters reflectively for the few models without @JsonClass.
-keepclassmembers class ** {
    @com.squareup.moshi.FromJson <methods>;
    @com.squareup.moshi.ToJson <methods>;
}
-keep @com.squareup.moshi.JsonQualifier @interface *
-keepclassmembers class kotlin.Metadata { public <methods>; }

# Retrofit keeps generic signatures on its service interfaces.
-keepattributes Signature, InnerClasses, EnclosingMethod
-keepattributes RuntimeVisibleAnnotations, RuntimeVisibleParameterAnnotations
-keep,allowobfuscation,allowshrinking interface retrofit2.Call
-keep,allowobfuscation,allowshrinking class retrofit2.Response
-keep,allowobfuscation,allowshrinking class kotlin.coroutines.Continuation

# Room generates implementations referenced only from the generated code.
-keep class * extends androidx.room.RoomDatabase { <init>(); }

# Hilt / Dagger.
-keep class dagger.hilt.** { *; }
-keep class javax.inject.** { *; }
