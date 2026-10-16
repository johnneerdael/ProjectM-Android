# The native library binds its functions by class and method name (Java_nl_neerdael_projectm_core_ProjectMJNI_*).
-keep class nl.neerdael.projectm.core.ProjectMJNI {
    native <methods>;
}

# xCrash registers native methods and resolves callbacks by class/method name.
-keep class xcrash.NativeHandler {
    native <methods>;
    void crashCallback(...);
    void traceCallback(...);
    void traceCallbackBeforeDump(...);
}
