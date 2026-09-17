// apple-notes-pkm-helper — the one process that sends Apple Events to Notes
// on behalf of apple-notes-pkm.py.
//
// Contract: no arguments; exactly one JSON object on stdin; one JSON object on
// stdout; diagnostics on stderr. The only program it can run is notes.jxa,
// embedded at link time into the __TEXT,__notes_jxa section, so the request
// can pick an `op` inside that program but never a script, application, path,
// or command. No network, listener, daemon, or generic script evaluation.
//
// TCC attributes Apple Events to a process's *responsible* process, which for
// a subprocess is normally the terminal, Herdr, or the python3 that launched
// it. The helper therefore re-spawns itself once with the responsibility
// disclaimed, so macOS records the grant against this bundle's identity.
//
// Exit codes: 0 ran (stdout JSON carries ok:true/false) · 1 internal failure
// · 2 usage (arguments given, or stdin is not one JSON object).
#import <Foundation/Foundation.h>
#import <OSAKit/OSAKit.h>
#import <mach-o/dyld.h>
#import <mach-o/getsect.h>
#import <mach-o/ldsyms.h>
#import <spawn.h>
#import <sys/wait.h>

extern int responsibility_spawnattrs_setdisclaim(posix_spawnattr_t *attrs, int disclaim);
extern char **environ;

static const char *kDisclaimedMarker = "APPLE_NOTES_PKM_HELPER_DISCLAIMED";

static int emit(NSDictionary *payload, int status) {
    NSData *data = [NSJSONSerialization dataWithJSONObject:payload options:0 error:NULL];
    NSFileHandle *out = [NSFileHandle fileHandleWithStandardOutput];
    [out writeData:data];
    [out writeData:[NSData dataWithBytes:"\n" length:1]];
    return status;
}

static int fail(NSString *message, int status) {
    return emit(@{@"ok": @NO, @"error": message, @"helper": @"apple-notes-pkm-helper"}, status);
}

// Re-run this executable as its own responsible process and relay its exit code.
static int respawnDisclaimed(char *const argv[]) {
    char path[PATH_MAX];
    uint32_t size = sizeof(path);
    if (_NSGetExecutablePath(path, &size) != 0) return fail(@"could not resolve own executable path", 1);
    posix_spawnattr_t attrs;
    posix_spawnattr_init(&attrs);
    if (responsibility_spawnattrs_setdisclaim(&attrs, 1) != 0) {
        posix_spawnattr_destroy(&attrs);
        return fail(@"could not disclaim responsibility for the Notes automation process", 1);
    }
    setenv(kDisclaimedMarker, "1", 1);
    pid_t pid = 0;
    int rc = posix_spawn(&pid, path, NULL, &attrs, argv, environ);
    posix_spawnattr_destroy(&attrs);
    if (rc != 0) return fail([NSString stringWithFormat:@"posix_spawn failed: %s", strerror(rc)], 1);
    int status = 0;
    while (waitpid(pid, &status, 0) < 0 && errno == EINTR) {}
    return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}

static NSString *embeddedProgram(void) {
    unsigned long size = 0;
    uint8_t *bytes = getsectiondata(&_mh_execute_header, "__TEXT", "__notes_jxa", &size);
    if (!bytes || size == 0) return nil;
    return [[NSString alloc] initWithBytes:bytes length:size encoding:NSUTF8StringEncoding];
}

int main(int argc, char *argv[]) {
    @autoreleasepool {
        if (argc != 1) return fail(@"usage: apple-notes-pkm-helper takes no arguments; write one JSON request to stdin", 2);
        if (getenv(kDisclaimedMarker) == NULL) return respawnDisclaimed(argv);

        NSData *input = [[NSFileHandle fileHandleWithStandardInput] readDataToEndOfFile];
        NSError *error = nil;
        id request = input.length ? [NSJSONSerialization JSONObjectWithData:input options:0 error:&error] : nil;
        if (![request isKindOfClass:[NSDictionary class]]) {
            return fail([NSString stringWithFormat:@"request must be one JSON object on stdin%@",
                         error ? [@": " stringByAppendingString:error.localizedDescription] : @""], 2);
        }
        NSData *canonical = [NSJSONSerialization dataWithJSONObject:request options:0 error:&error];
        if (!canonical) return fail(@"request could not be re-serialized", 2);

        NSString *source = embeddedProgram();
        if (!source) return fail(@"embedded notes.jxa program is missing from this build", 1);
        OSAScript *script = [[OSAScript alloc] initWithSource:source language:[OSALanguage languageForName:@"JavaScript"]];
        NSDictionary *scriptError = nil;
        if (![script compileAndReturnError:&scriptError]) {
            return fail([NSString stringWithFormat:@"embedded program failed to compile: %@", scriptError[OSAScriptErrorMessageKey] ?: scriptError], 1);
        }
        NSString *requestJSON = [[NSString alloc] initWithData:canonical encoding:NSUTF8StringEncoding];
        NSAppleEventDescriptor *result = [script executeHandlerWithName:@"run" arguments:@[@[requestJSON]] error:&scriptError];
        if (!result) {
            // notes.jxa catches its own errors; reaching here means the runtime itself failed.
            NSString *message = scriptError[OSAScriptErrorMessageKey] ?: [scriptError description] ?: @"unknown error";
            NSNumber *number = scriptError[OSAScriptErrorNumberKey];
            return emit(@{@"ok": @NO, @"error": message, @"errorNumber": number ?: [NSNull null], @"helper": @"apple-notes-pkm-helper"}, 0);
        }
        NSString *output = result.stringValue ?: @"";
        NSFileHandle *out = [NSFileHandle fileHandleWithStandardOutput];
        [out writeData:[output dataUsingEncoding:NSUTF8StringEncoding]];
        [out writeData:[NSData dataWithBytes:"\n" length:1]];
        return 0;
    }
}
