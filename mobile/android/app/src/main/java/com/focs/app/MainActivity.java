package com.focs.app;

import android.os.Bundle;
import android.webkit.WebView;
import androidx.activity.OnBackPressedCallback;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        // Back goes to the page before; from the first page it puts Focs in the background instead of closing it.
        getOnBackPressedDispatcher()
            .addCallback(
                this,
                new OnBackPressedCallback(true) {
                    @Override
                    public void handleOnBackPressed() {
                        WebView view = getBridge() == null ? null : getBridge().getWebView();
                        if (view != null && view.canGoBack()) {
                            view.goBack();
                        } else {
                            moveTaskToBack(true);
                        }
                    }
                }
            );
    }
}
